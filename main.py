# main.py

import asyncio
import traceback

from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from playwright.async_api import async_playwright


# ==================================================
# FastAPI
# ==================================================
app = FastAPI(
    title="Kunsan Daily Check API",
    version="5.0.0"
)


# ==================================================
# 설정
# ==================================================
LOGIN_URL = "https://kis.kunsan.ac.kr/login.do"

run_lock = asyncio.Lock()


# ==================================================
# 요청 모델
# ==================================================
class CheckRequest(BaseModel):

    user_id: str = Field(..., min_length=1)
    user_pw: str = Field(..., min_length=1)


# ==================================================
# 루트
# ==================================================
@app.get("/")
async def root():

    return {
        "ok": True,
        "message": "Kunsan Daily Check API Running"
    }


@app.get("/health")
async def health():

    return {
        "ok": True,
        "status": "healthy"
    }


# ==================================================
# 실제 완료 검증 함수
# ==================================================
async def verify_daily_check(new_tab) -> bool:

    today = datetime.now().strftime("%Y-%m-%d")

    try:

        await asyncio.sleep(5)

        body_text = await new_tab.locator(
            "body"
        ).inner_text()

        print("================================================")
        print("실제 체크 완료 검증")
        print("================================================")
        print("오늘 날짜:", today)

        if (
            today in body_text and
            "체크완료" in body_text
        ):

            print("실제 체크 완료 확인 성공")

            return True

        print("체크완료 문자열 미검출")

        return False

    except Exception as e:

        print("검증 실패:", e)

        return False


# ==================================================
# 메인 자동화
# ==================================================
async def perform_check(
    user_id: str,
    user_pw: str
) -> Dict[str, Any]:

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )

        context = await browser.new_context(
            viewport={
                "width": 1280,
                "height": 800
            },
            java_script_enabled=True,
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        try:

            print("================================================")
            print("1. 로그인 페이지 접속")
            print("================================================")

            await page.goto(
                LOGIN_URL,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await asyncio.sleep(3)

            # ==================================================
            # 로그인 정보 입력
            # ==================================================
            id_input = page.locator(
                "input#id, input[name='id'], input[type='text']"
            ).first

            await id_input.wait_for(
                state="visible",
                timeout=15000
            )

            await id_input.fill(user_id)

            pw_input = page.locator(
                "input#pw, input[name='pw'], input[type='password']"
            ).first

            await pw_input.fill(user_pw)

            print("아이디 / 비밀번호 입력 완료")

            # ==================================================
            # 로그인 버튼
            # ==================================================
            login_clicked = False

            for selector in [
                "#loginBtn",
                "button:has-text('로그인')",
                "input[value='로그인']"
            ]:

                try:

                    btn = page.locator(
                        selector
                    ).first

                    if await btn.count() > 0:

                        await btn.click(
                            force=True
                        )

                        login_clicked = True

                        print(
                            f"로그인 버튼 클릭 성공: {selector}"
                        )

                        break

                except Exception:
                    continue

            if not login_clicked:

                print("엔터 로그인 fallback")

                await page.keyboard.press(
                    "Enter"
                )

            await asyncio.sleep(5)

            # ==================================================
            # 중복 로그인 처리
            # ==================================================
            try:

                confirm_btn = page.get_by_role(
                    "button",
                    name="확인"
                )

                if await confirm_btn.count() > 0:

                    await confirm_btn.first.click()

                    print("중복 로그인 확인 완료")

            except Exception:
                pass

            await asyncio.sleep(5)

            # ==================================================
            # 통합정보
            # ==================================================
            print("================================================")
            print("2. 통합정보 진입")
            print("================================================")

            async with context.expect_page(
                timeout=15000
            ) as new_page_info:

                await page.get_by_text(
                    "통합정보"
                ).first.click()

            new_tab = await new_page_info.value

            await new_tab.wait_for_load_state(
                "domcontentloaded"
            )

            print("통합정보 새창 진입 완료")

            await asyncio.sleep(5)

            # ==================================================
            # 학생서비스
            # ==================================================
            print("================================================")
            print("3. 학생서비스")
            print("================================================")

            await new_tab.get_by_text(
                "학생서비스"
            ).first.click()

            await asyncio.sleep(5)

            # ==================================================
            # MY MENU
            # ==================================================
            print("================================================")
            print("4. MY MENU")
            print("================================================")

            await new_tab.get_by_text(
                "MY MENU"
            ).first.click()

            await asyncio.sleep(3)

            # ==================================================
            # 일일체크신청
            # ==================================================
            print("================================================")
            print("5. 일일체크신청")
            print("================================================")

            await new_tab.get_by_text(
                "일일체크신청"
            ).last.click()

            await asyncio.sleep(8)

            # ==================================================
            # 이미 완료 여부 먼저 확인
            # ==================================================
            page_text = await new_tab.locator(
                "body"
            ).inner_text()

            today = datetime.now().strftime(
                "%Y-%m-%d"
            )

            if (
                today in page_text and
                "체크완료" in page_text
            ):

                print("오늘 이미 완료 상태")

                return {
                    "ok": True,
                    "status": "skipped",
                    "message": "오늘 이미 완료됨"
                }

            # ==================================================
            # 저장 버튼
            # ==================================================
            print("================================================")
            print("6. 저장 버튼 클릭")
            print("================================================")

            save_success = False

            all_frames = [new_tab] + list(
                new_tab.frames
            )

            for frame in all_frames:

                try:

                    candidates = frame.locator(
                        """
                        button:has-text('저장'),
                        input[value='저장'],
                        .btn_save,
                        a:has-text('저장'),
                        span:has-text('저장'),
                        text=저장
                        """
                    )

                    count = await candidates.count()

                    print("저장 후보 개수:", count)

                    for i in range(count):

                        try:

                            target = candidates.nth(i)

                            visible = await target.is_visible()

                            if not visible:
                                continue

                            await target.scroll_into_view_if_needed()

                            await asyncio.sleep(1)

                            try:

                                await target.click(
                                    force=True,
                                    timeout=5000
                                )

                            except Exception:

                                await target.evaluate(
                                    "(el) => el.click()"
                                )

                            print(
                                f"저장 버튼 클릭 성공 index={i}"
                            )

                            save_success = True

                            break

                        except Exception as inner_error:

                            print(
                                "inner_error:",
                                inner_error
                            )

                    if save_success:
                        break

                except Exception as frame_error:

                    print(
                        "frame_error:",
                        frame_error
                    )

            # ==================================================
            # fallback
            # ==================================================
            if not save_success:

                print("엔터 fallback 저장")

                await new_tab.keyboard.press(
                    "Enter"
                )

                await asyncio.sleep(3)

                save_success = True

            if not save_success:

                raise RuntimeError(
                    "저장 버튼 클릭 실패"
                )

            # ==================================================
            # 저장 후 충분한 대기
            # ==================================================
            print("저장 후 서버 반영 대기 중...")

            await asyncio.sleep(8)

            # ==================================================
            # 팝업 처리
            # ==================================================
            print("================================================")
            print("7. 팝업 처리")
            print("================================================")

            for _ in range(5):

                try:

                    btns = new_tab.locator(
                        "button, "
                        "input[type='button'], "
                        "input[type='submit'], "
                        "a.btn"
                    )

                    count = await btns.count()

                    for i in range(count):

                        target = btns.nth(i)

                        txt = ""

                        try:
                            txt = await target.inner_text()
                        except:
                            pass

                        val = (
                            await target.get_attribute(
                                "value"
                            ) or ""
                        )

                        merged = txt + val

                        if any(
                            x in merged
                            for x in [
                                "예",
                                "확인",
                                "OK",
                                "yes",
                                "Yes"
                            ]
                        ):

                            await target.click(
                                force=True
                            )

                            print(
                                f"팝업 처리 성공: {merged}"
                            )

                except Exception:
                    pass

                await asyncio.sleep(1)

            # ==================================================
            # 실제 완료 검증
            # ==================================================
            verified = await verify_daily_check(
                new_tab
            )

            if not verified:

                raise RuntimeError(
                    "저장은 눌렸지만 실제 체크완료가 확인되지 않았습니다."
                )

            # ==================================================
            # 닫기
            # ==================================================
            try:

                await new_tab.get_by_text(
                    "닫기"
                ).first.click()

            except Exception:
                pass

            await asyncio.sleep(2)

            # ==================================================
            # SUCCESS
            # ==================================================
            print("================================================")
            print("SUCCESS")
            print("================================================")

            return {
                "ok": True,
                "status": "success",
                "message": "일일체크 완료",
                "detail": {
                    "user_id": user_id,
                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }
            }

        except Exception as e:

            print("================================================")
            print("ERROR")
            print("================================================")

            print(traceback.format_exc())

            try:

                screenshot_name = (
                    f"error_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    f".png"
                )

                await page.screenshot(
                    path=screenshot_name,
                    full_page=True
                )

                print(
                    "스크린샷 저장:",
                    screenshot_name
                )

            except Exception:
                pass

            return {
                "ok": False,
                "status": "error",
                "message": str(e)
            }

        finally:

            await context.close()
            await browser.close()


# ==================================================
# API
# ==================================================
@app.post("/api/check")
async def api_check(req: CheckRequest):

    async with run_lock:

        result = await perform_check(
            req.user_id,
            req.user_pw
        )

        return result


# ==================================================
# 실행
# uvicorn main:app --host 0.0.0.0 --port 10000
# ==================================================
