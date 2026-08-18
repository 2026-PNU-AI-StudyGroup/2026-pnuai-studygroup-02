# backend/services/recipe_collector.py

# [RAG-DATA] 시은 담당. 한국어 주석 필수

import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from urllib.parse import unquote


# [RAG-DATA] 프로젝트 루트의 .env 파일을 불러온다.
load_dotenv(override=True)

RDA_API_KEY = unquote(
    os.getenv("RDA_RECIPE_API_KEY", "")
)
FOODSAFETY_API_KEY = unquote(
    os.getenv("FOODSAFETY_RECIPE_API_KEY", "")
)


# [RAG-DATA] 수집된 레시피를 저장할 위치
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "recipe_corpus"
    / "recipes.jsonl"
)


# [RAG-DATA] 농촌진흥청 음식, 재료 및 조리 정보 API
RDA_COOK_API_URL = (
    "http://apis.data.go.kr/1390803/AgriFood/"
    "FdCkry1/getKoreanFoodFdCkryList1"
)

# [RAG-DATA] 농촌진흥청 음식 및 재료 정보 API
RDA_FOOD_API_URL = (
    "http://apis.data.go.kr/1390803/AgriFood/"
    "FdFood1/getKoreanFoodFdFoodList1"
)

RDA_SOURCE_NAME = (
    "농촌진흥청 국립식량과학원 "
    "농식품 식단관리(메뉴젠)"
)

RDA_SOURCE_URL = (
    "https://www.data.go.kr/data/15143500/openapi.do"
)

# [RAG-DATA] 식품안전나라 조리식품의 레시피 DB
FOODSAFETY_SERVICE_ID = "COOKRCP01"

FOODSAFETY_SOURCE_NAME = "식품안전나라 조리식품의 레시피 DB"

FOODSAFETY_SOURCE_URL = (
    "https://www.foodsafetykorea.go.kr/api/openApiInfo.do"
    "?menu_grp=MENU_GRP31&menu_no=661&svc_no=COOKRCP01"
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

# [RAG-DATA] httpx가 인증키가 포함된 전체 요청 URL을 INFO 로그에 남기지 않도록 한다.
logging.getLogger("httpx").setLevel(logging.WARNING)


def request_with_retry(
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> httpx.Response | None:
    """
    [RAG-DATA] API 요청에 실패하면 1회 재시도한다.
    두 번째 요청까지 실패하면 None을 반환한다.
    """

    for attempt in range(2):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=20.0,
            )
            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            if attempt == 0:
                logger.warning(
                    "[RAG-DATA] API 요청 실패(status=%s). 1회 재시도합니다. api=%s",
                    status_code,
                    url,
                )
                time.sleep(1)
            else:
                logger.error(
                    "[RAG-DATA] API 재시도 실패(status=%s). 해당 요청을 건너뜁니다. api=%s",
                    status_code,
                    url,
                )

        except httpx.RequestError:
            if attempt == 0:
                logger.warning(
                    "[RAG-DATA] API 연결 실패. 1회 재시도합니다. api=%s",
                    url,
                )
                time.sleep(1)
            else:
                logger.error(
                    "[RAG-DATA] API 연결 재시도 실패. 해당 요청을 건너뜁니다. api=%s",
                    url,
                )

    return None


def clean_text(value: Any) -> str:
    """
    [RAG-DATA] 문자열의 불필요한 공백을 제거한다.
    """

    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def split_foodsafety_ingredients(raw: str) -> list[str]:
    """
    [RAG-DATA] 식품안전나라의 재료 문자열을 간단한 목록으로 변환한다.
    """

    raw = raw.replace("\r", "\n")

    parts = re.split(r"[,;\n]+", raw)

    result: list[str] = []

    for part in parts:
        cleaned = clean_text(part)

        if cleaned and cleaned not in result:
            result.append(cleaned)

    return result


def normalize_foodsafety_recipe(row: dict[str, Any]) -> dict[str, Any] | None:
    """
    [RAG-DATA] 식품안전나라 응답 한 건을 공통 레시피 형식으로 변환한다.
    """

    title = clean_text(row.get("RCP_NM"))

    if not title:
        return None

    ingredients_raw = clean_text(row.get("RCP_PARTS_DTLS"))

    ingredients = split_foodsafety_ingredients(
        ingredients_raw
    )

    steps: list[str] = []

    for index in range(1, 21):
        key = f"MANUAL{index:02d}"

        step = clean_text(row.get(key))

        if step:
            steps.append(step)

    if not steps:
        return None

    return {
        "title": title,
        "ingredients": ingredients,
        "steps": steps,
        "source": {
            "api_name": FOODSAFETY_SOURCE_NAME,
            "url": FOODSAFETY_SOURCE_URL,
        },
    }


def fetch_foodsafety_recipes(
    page_size: int = 1000,
) -> list[dict[str, Any]]:
    """
    [RAG-DATA] 식품안전나라 COOKRCP01 API에서
    전체 레시피를 페이지 단위로 수집한다.
    """

    if not FOODSAFETY_API_KEY:
        logger.error(
            "[RAG-DATA] FOODSAFETY_RECIPE_API_KEY가 없습니다."
        )
        return []

    recipes: list[dict[str, Any]] = []

    start_index = 1

    while True:
        end_index = start_index + page_size - 1

        url = (
            "http://openapi.foodsafetykorea.go.kr/api/"
            f"{FOODSAFETY_API_KEY}/"
            f"{FOODSAFETY_SERVICE_ID}/json/"
            f"{start_index}/{end_index}"
        )

        response = request_with_retry(url)

        if response is None:
            break

        try:
            payload = response.json()
        except ValueError:
            logger.error(
                "[RAG-DATA] 식품안전나라 JSON 파싱 실패"
            )
            break

        service_data = payload.get(
            FOODSAFETY_SERVICE_ID,
            {},
        )

        rows = service_data.get("row", [])

        if not rows:
            break

        for row in rows:
            normalized = normalize_foodsafety_recipe(
                row
            )

            if normalized:
                recipes.append(normalized)

        logger.info(
            "[RAG-DATA] 식품안전나라 %s~%s 수집 완료",
            start_index,
            end_index,
        )

        if len(rows) < page_size:
            break

        start_index += page_size

    return recipes


def xml_text(
    element: ET.Element,
    tag_name: str,
) -> str:
    """
    [RAG-DATA] XML 요소에서 원하는 태그의 텍스트를 찾는다.
    """

    for child in element.iter():
        tag = child.tag.split("}")[-1]

        if tag == tag_name:
            return clean_text(child.text)

    return ""


def xml_local_name(element: ET.Element) -> str:
    """
    [RAG-DATA] XML namespace가 있더라도 실제 태그 이름만 반환한다.
    """

    return element.tag.split("}")[-1]

def xml_raw_text(
    element: ET.Element,
    tag_name: str,
) -> str:
    """
    [RAG-DATA] XML의 원본 줄바꿈을 유지한 채
    지정한 태그의 문자열을 반환한다.
    """

    for child in element.iter():
        if xml_local_name(child) == tag_name:
            if child.text is None:
                return ""

            return (
                child.text
                .replace("\r\n", "\n")
                .replace("\r", "\n")
                .strip()
            )

    return ""


def find_xml_element(
    element: ET.Element,
    tag_name: str,
) -> ET.Element | None:
    """
    [RAG-DATA] 하위 XML에서 지정한 태그를 찾아 반환한다.
    """

    for child in element.iter():
        if xml_local_name(child) == tag_name:
            return child

    return None


def parse_rda_ingredients(
    item: ET.Element,
) -> list[str]:
    """
    [RAG-DATA] 농촌진흥청 음식 및 재료 정보에서
    재료명과 중량을 추출한다.
    """

    ingredients: list[str] = []

    food_list = find_xml_element(
        item,
        "food_List",
    )

    # [RAG-DATA] food_List 안에 여러 food가 들어 있는 구조
    if food_list is not None:
        food_nodes = [
            element
            for element in food_list.iter()
            if xml_local_name(element) == "food"
        ]

    else:
        # [RAG-DATA] API 응답 구조가 단일 재료 형식인 경우도 처리한다.
        food_nodes = [item]

    for food in food_nodes:
        name = xml_text(
            food,
            "food_Nm",
        )

        weight = xml_text(
            food,
            "food_Wgh",
        )

        if not name:
            continue

        if name.lower() == "null":
            continue

        ingredient = name

        if (
            weight
            and weight.lower() != "null"
            and weight != "0"
        ):
            ingredient = (
                f"{name} {weight}g"
            )

        if ingredient not in ingredients:
            ingredients.append(
                ingredient
            )

    return ingredients

def fetch_rda_ingredients(
    fd_code: str,
    food_name: str,
) -> list[str]:
    """
    [RAG-DATA] 농촌진흥청 음식 및 재료 정보 API에서
    특정 음식의 재료 목록을 조회한다.
    """

    page = 1
    page_size = 10

    while True:
        params = {
            "serviceKey": RDA_API_KEY,
            "page_No": str(page),
            "food_Name": food_name,
            "service_Type": "xml",
            "Page_Size": str(page_size),
        }

        response = request_with_retry(
            RDA_FOOD_API_URL,
            params=params,
        )

        if response is None:
            logger.warning(
                "[RAG-DATA] 재료 API 요청 실패. "
                "fd_Code=%s title=%s",
                fd_code,
                food_name,
            )
            return []

        try:
            root = ET.fromstring(response.text)

        except ET.ParseError:
            logger.warning(
                "[RAG-DATA] 재료 API XML 파싱 실패. "
                "fd_Code=%s title=%s",
                fd_code,
                food_name,
            )
            return []

        result_code = xml_text(
            root,
            "result_Code",
        )

        if result_code == "301":
            return []

        if result_code != "200":
            logger.warning(
                "[RAG-DATA] 재료 API 오류. "
                "code=%s message=%s",
                result_code,
                xml_text(root, "result_Msg"),
            )
            return []

        items = [
            element
            for element in root.iter()
            if xml_local_name(element) == "item"
        ]

        for item in items:
            item_fd_code = xml_text(
                item,
                "fd_Code",
            )

            if item_fd_code != fd_code:
                continue

            ingredients = parse_rda_ingredients(
                item
            )

            if ingredients:
                return ingredients

        raw_total = xml_text(
            root,
            "total_Count",
        )

        try:
            total_count = int(raw_total)
        except ValueError:
            total_count = 0

        if (
            total_count == 0
            or page * page_size >= total_count
        ):
            break

        page += 1

    return []


def parse_rda_cooking_steps(
    item: ET.Element,
) -> list[str]:
    """
    [RAG-DATA] 농촌진흥청 ckry_List의 조리정보를 단계 목록으로 변환한다.

    조리 상세 태그는 데이터에 따라 여러 필드로 구성될 수 있으므로,
    ckry_List 안의 각 조리 항목에서 코드/순번 필드를 제외한
    설명성 문자열을 순서대로 합쳐 한 단계로 만든다.
    """

    ckry_list = find_xml_element(item, "ckry_List")

    if ckry_list is None:
        return []

    # [RAG-DATA] <ckry_List></ckry_List>처럼 비어 있는 음식은 조리 단계가 없다.
    entries = list(ckry_list)

    if not entries:
        return []

    steps: list[str] = []

    # [RAG-DATA] 조리 설명이 아닌 식별/순번 계열 태그는 제외한다.
    skip_tokens = (
        "code",
        "_no",
        "no_",
        "seq",
        "id",
        "cnt",
    )

    for entry in entries:
        values: list[str] = []

        # [RAG-DATA] entry 자체가 leaf인 경우도 처리하기 위해 iter()를 사용한다.
        for leaf in entry.iter():
            if list(leaf):
                continue

            tag = xml_local_name(leaf)
            lowered_tag = tag.lower()
            value = clean_text(leaf.text)

            if not value or value.lower() == "null":
                continue

            if any(token in lowered_tag for token in skip_tokens):
                continue

            # 숫자만 있는 값은 조리 단계 설명으로 사용하지 않는다.
            if re.fullmatch(r"[0-9.]+", value):
                continue

            if value not in values:
                values.append(value)

        if values:
            step = " ".join(values)

            if step not in steps:
                steps.append(step)

    return steps


def normalize_rda_item(
    item: ET.Element,
) -> dict[str, Any] | None:
    """
    [RAG-DATA] 농촌진흥청 조리정보 한 건을
    공통 레시피 형식으로 변환한다.
    """

    fd_code = xml_text(
        item,
        "fd_Code",
    )

    title = xml_text(
        item,
        "fd_Nm",
    )

    # [RAG-DATA] 조리법의 줄바꿈을 유지한다.
    cooking_text = xml_raw_text(
        item,
        "ckry_Sumry_Info",
    )

    if (
        not fd_code
        or not title
        or not cooking_text
    ):
        return None

    # [RAG-DATA] 아직 등록되지 않은 조리법은 제외한다.
    if (
        "추후 정보를 갱신 예정"
        in cooking_text
    ):
        return None

    # [RAG-DATA] 줄바꿈 또는 여러 칸의 공백을
    # 기준으로 실제 조리 단계를 분리한다.
    raw_steps = re.split(
        r"\n+| {2,}",
        cooking_text,
    )

    steps: list[str] = []

    for raw_step in raw_steps:
        step = clean_text(
            raw_step
        )

        if (
            step
            and step not in steps
        ):
            steps.append(
                step
            )

    if not steps:
        return None

    return {
        # [RAG-DATA] 두 API를 연결할 때만 사용하는 내부값
        "_fd_code": fd_code,

        "title": title,

        # [RAG-DATA] 이후 재료 API 결과로 채운다.
        "ingredients": [],

        "steps": steps,

        "source": {
            "api_name": RDA_SOURCE_NAME,
            "url": RDA_SOURCE_URL,
        },
    }


def fetch_rda_recipes(
    page_size: int = 10,
) -> list[dict[str, Any]]:
    """
    [RAG-DATA] 농촌진흥청 음식 및 조리정보 API에서
    실제 조리법 데이터를 수집한다.

    재료정보 API는 현재 인증 문제로 인해 호출하지 않고,
    ingredients는 빈 배열로 저장한다.
    """

    if not RDA_API_KEY:
        logger.error(
            "[RAG-DATA] RDA_RECIPE_API_KEY가 없습니다."
        )
        return []

    recipes: list[dict[str, Any]] = []

    page = 1
    total_count: int | None = None

    while True:
        params = {
            "serviceKey": RDA_API_KEY,
            "page_No": str(page),
            "ckry_Name": "%",
            "service_Type": "xml",
            "Page_Size": str(page_size),
        }

        response = request_with_retry(
            RDA_COOK_API_URL,
            params=params,
        )

        if response is None:
            logger.error(
                "[RAG-DATA] 농촌진흥청 조리정보 요청 실패. "
                "page=%s",
                page,
            )
            break

        try:
            root = ET.fromstring(
                response.text
            )

        except ET.ParseError:
            logger.error(
                "[RAG-DATA] 농촌진흥청 조리정보 XML 파싱 실패. "
                "page=%s",
                page,
            )
            break

        result_code = xml_text(
            root,
            "result_Code",
        )

        if result_code != "200":
            logger.error(
                "[RAG-DATA] 농촌진흥청 조리정보 API 오류. "
                "page=%s code=%s message=%s",
                page,
                result_code,
                xml_text(
                    root,
                    "result_Msg",
                ),
            )
            break

        if total_count is None:
            raw_total = xml_text(
                root,
                "total_Count",
            )

            try:
                total_count = int(
                    raw_total
                )
            except ValueError:
                total_count = 0

            logger.info(
                "[RAG-DATA] 농촌진흥청 조리정보 총 %s건",
                total_count,
            )

        items = [
            element
            for element in root.iter()
            if xml_local_name(element) == "item"
        ]

        if not items:
            break

        page_success_count = 0

        for item in items:
            normalized = normalize_rda_item(
                item
            )

            if normalized is None:
                continue

            # [RAG-DATA] 내부 연결용 fd_Code 제거
            normalized.pop(
                "_fd_code",
                None,
            )

            # [RAG-DATA] 재료 API 인증 문제가 해결되기 전까지
            # 빈 배열로 저장한다.
            normalized["ingredients"] = []

            recipes.append(
                normalized
            )

            page_success_count += 1

        logger.info(
            "[RAG-DATA] 농촌진흥청 %s페이지 완료 "
            "(원본 %s건 / 저장 레시피 %s건)",
            page,
            len(items),
            page_success_count,
        )

        if (
            total_count is not None
            and page * page_size >= total_count
        ):
            break

        page += 1

    logger.info(
        "[RAG-DATA] 농촌진흥청 정상 레시피 %s개 수집",
        len(recipes),
    )

    return recipes

def save_jsonl(
    recipes: list[dict[str, Any]],
) -> None:
    """
    [RAG-DATA] 정규화한 레시피를 JSONL 형식으로 저장한다.
    """

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        for recipe in recipes:
            json.dump(
                recipe,
                file,
                ensure_ascii=False,
            )
            file.write("\n")

    logger.info(
        "[RAG-DATA] 총 %s개의 레시피를 저장했습니다. path=%s",
        len(recipes),
        OUTPUT_PATH,
    )


def collect_recipes() -> None:
    """
    [RAG-DATA] 두 공공 API에서 데이터를 수집하고
    하나의 JSONL 파일로 저장한다.
    """

    logger.info(
        "[RAG-DATA] 레시피 데이터 수집을 시작합니다."
    )

    rda_recipes = fetch_rda_recipes()

    logger.info(
        "[RAG-DATA] 농촌진흥청 레시피 %s개 수집",
        len(rda_recipes),
    )

    foodsafety_recipes = (
        fetch_foodsafety_recipes()
    )

    logger.info(
        "[RAG-DATA] 식품안전나라 레시피 %s개 수집",
        len(foodsafety_recipes),
    )

    recipes = (
        rda_recipes
        + foodsafety_recipes
    )

    save_jsonl(recipes)



if __name__ == "__main__":
    collect_recipes()