import logging
import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from pages.main_page import MainPage
from pages.search_page import SearchPage

logger = logging.getLogger(__name__)


@pytest.mark.smoke
class TestAlbamonSmokeSearch:
    """알바몬 웹 핵심 기능(메인 로드 -> 키워드 검색 -> 공고 상세 진입) UI 스모크 테스트 스위트.

    배포 직후 서비스의 핵심 사용자 여정(Critical User Journey)이 정상 동작하는지
    빠르게 검증하기 위한 자동화 테스트 시나리오입니다.
    """

    SEARCH_KEYWORD = "카페"

    def test_tc01_main_page_load_verification(self, driver: WebDriver) -> None:
        """TC_01_메인페이지_정상_로드_검증:
        메인 페이지 접속 후 브라우저 타이틀 및 검색창/헤더 UI 요소가 정상 노출되는지 검증합니다.
        """
        main_page = MainPage(driver)

        # Given & When: 알바몬 메인 페이지 접속
        main_page.open()

        # Then 1: 페이지 타이틀에 '알바몬' 브랜드명이 포함되어 있는지 검증
        page_title = main_page.get_title()
        logger.info(f"확인된 메인 페이지 타이틀: '{page_title}'")
        assert "알바몬" in page_title or "albamon" in main_page.get_current_url().lower(), (
            f"메인 페이지 타이틀 또는 URL이 예상과 다릅니다. Title: {page_title}, URL: {main_page.get_current_url()}"
        )

        # Then 2: 상단 헤더 및 통합 검색창 UI 요소가 화면에 정상 노출되는지 검증
        assert main_page.is_header_displayed(), "메인 페이지 상단 헤더 영역이 노출되지 않았습니다."
        assert main_page.is_search_input_displayed(), "메인 페이지 통합 검색창 UI가 노출되지 않았습니다."

    def test_tc02_keyword_search_and_results_verification(self, driver: WebDriver) -> None:
        """TC_02_키워드_검색_및_결과_노출_검증:
        검색창에 '카페' 입력 후 검색 실행 -> 검색 결과 페이지로 이동되었는지 및
        채용 공고 리스트가 1개 이상 노출되는지 검증합니다.
        """
        main_page = MainPage(driver)
        search_page = SearchPage(driver)

        # Given: 알바몬 메인 페이지 접속
        main_page.open()

        # When: 검색창에 키워드('카페') 입력 후 검색 실행
        main_page.search_keyword(self.SEARCH_KEYWORD)
        search_page.wait_until_loaded()

        # Then 1: 검색 결과 페이지로 정상 이동되었는지 검증
        assert search_page.is_search_result_page(self.SEARCH_KEYWORD), (
            f"검색 결과 페이지로 정상 이동하지 못했습니다. 현재 URL: {search_page.get_current_url()}"
        )

        # Then 2: 검색 결과에 채용 공고 리스트가 최소 1개 이상 노출되는지 검증
        job_count = search_page.get_job_postings_count()
        logger.info(f"'{self.SEARCH_KEYWORD}' 키워드 검색 결과 노출 공고 수: {job_count}건")
        assert job_count >= 1, (
            f"'{self.SEARCH_KEYWORD}' 검색 결과 공고가 1개 이상 노출되어야 하나 {job_count}개 탐색되었습니다."
        )

    def test_tc03_job_detail_page_navigation_verification(self, driver: WebDriver) -> None:
        """TC_03_공고_상세페이지_진입_검증:
        검색 결과 리스트에서 첫 번째 채용 공고 클릭 -> 상세 페이지 정상 진입 여부를 검증합니다.
        """
        main_page = MainPage(driver)
        search_page = SearchPage(driver)

        # Given: 메인 페이지 접속 후 키워드 검색을 통해 검색 결과 리스트 노출
        main_page.open()
        main_page.search_keyword(self.SEARCH_KEYWORD)
        search_page.wait_until_loaded()

        assert search_page.get_job_postings_count() >= 1, (
            "상세 페이지 진입 테스트를 위한 선행 검색 결과 공고가 존재하지 않습니다."
        )

        # When: 검색 결과의 첫 번째 채용 공고 클릭
        target_href = search_page.click_first_job_posting()

        # Then: 채용 공고 상세 페이지로 정상 진입했는지 검증
        assert search_page.is_job_detail_page_loaded(), (
            f"채용 공고 상세 페이지 진입 검증에 실패했습니다. "
            f"클릭한 공고 링크: {target_href}, 현재 URL: {search_page.get_current_url()}"
        )
