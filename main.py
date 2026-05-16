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
    version="3.0.0"
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
            # 로그인 입력
            # ==================================================
            print("로그인 정보 입력 시작")

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
            # 로그인 버튼 클릭
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

            # fallback
            if not login_clicked:

                print("엔터 로그인 fallback")

                await page.keyboard.press(
                    "Enter"
                )

            await asyncio.sleep(5)

            # ==================================================
            # 중복 로그인 팝업 처리
            # ==================================================
            print("중복 로그인 팝업 확인")

            try:

                confirm_btn = page.get_by_role(
                    "button",
                    name="확인"
                )

                if await confirm_btn.count() > 0:

                    await confirm_btn.first.click()

                    print(
                        "중복 로그인 확인 클릭 완료"
                    )

            except Exception:
                pass

            await asyncio.sleep(5)

            # ==================================================
            # 통합정보 클릭 + 새탭 감지
            # ==================================================
            print("================================================")
            print("2. 통합정보 새탭 열기")
            print("================================================")

            async with context.expect_page(
                timeout=10000
            ) as new_page_info:

                await page.get_by_text(
                    "통합정보"
                ).first.click()

            new_tab = await new_page_info.value

            await new_tab.wait_for_load_state(
                "domcontentloaded"
            )

            print("새탭 전환 완료")

            await asyncio.sleep(5)

            # ==================================================
            # 학생서비스 클릭
            # ==================================================
            print("================================================")
            print("3. 학생서비스 클릭")
            print("================================================")

            await new_tab.get_by_text(
                "학생서비스"
            ).first.click()

            print("학생서비스 클릭 성공")

            await asyncio.sleep(5)

            # ==================================================
            # MY MENU
            # ==================================================
            print("================================================")
            print("4. MY MENU 클릭")
            print("================================================")

            await new_tab.get_by_text(
                "MY MENU"
            ).first.click()

            print("MY MENU 클릭 성공")

            await asyncio.sleep(3)

            # ==================================================
            # 일일체크신청
            # ==================================================
            print("================================================")
            print("5. 일일체크신청 클릭")
            print("================================================")

            await new_tab.get_by_text(
                "일일체크신청"
            ).last.click()

            print("일일체크신청 클릭 성공")

            await asyncio.sleep(5)

            # ==================================================
            # 저장 버튼
            # ==================================================
            print("================================================")
            print("6. 저장 버튼 클릭")
            print("================================================")

            save_success = False

            try:

                save_button = new_tab.locator(
                    "button:has-text('저장'), "
                    "input[value='저장'], "
                    ".btn_save"
                ).first

                await save_button.wait_for(
                    state="visible",
                    timeout=10000
                )

                await save_button.click(
                    force=True
                )

                save_success = True

                print("일반 저장 버튼 클릭 성공")

            except Exception:

                print(
                    "프레임 내부 저장 버튼 탐색 시작"
                )

                for frame in new_tab.frames:

                    try:

                        target = frame.locator(
                            "button:has-text('저장'), "
                            "input[value='저장'], "
                            "text=저장"
                        ).first

                        if await target.count() > 0:

                            await target.click(
                                force=True
                            )

                            save_success = True

                            print(
                                "프레임 저장 버튼 클릭 성공"
                            )

                            break

                    except Exception:
                        continue

            if not save_success:

                raise RuntimeError(
                    "저장 버튼 클릭 실패"
                )

            await asyncio.sleep(3)

            # ==================================================
            # 엔터 입력
            # ==================================================
            print("엔터 입력")

            await new_tab.keyboard.press(
                "Enter"
            )

            await asyncio.sleep(2)

            # ==================================================
            # 예 / 확인 버튼 처리
            # ==================================================
            print("================================================")
            print("7. 최종 확인 팝업 처리")
            print("================================================")

            final_success = False

            for _ in range(5):

                # 메인 페이지 탐색
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

                            final_success = True

                            print(
                                f"메인 팝업 처리 성공: {merged}"
                            )

                            break

                except Exception:
                    pass

                # 프레임 탐색
                for frame in new_tab.frames:

                    try:

                        btns = frame.locator(
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

                                final_success = True

                                print(
                                    f"프레임 팝업 처리 성공: {merged}"
                                )

                                break

                    except Exception:
                        continue

                if final_success:
                    break

                await asyncio.sleep(1)

            # ==================================================
            # 닫기 버튼
            # ==================================================
            print("================================================")
            print("8. 닫기 버튼 처리")
            print("================================================")

            try:

                await new_tab.get_by_text(
                    "닫기"
                ).first.click()

                print("닫기 버튼 클릭 성공")

            except Exception:
                pass

            await asyncio.sleep(2)

            # ==================================================
            # 로그아웃
            # ==================================================
            print("================================================")
            print("9. 로그아웃")
            print("================================================")

            try:

                new_tab.on(
                    "dialog",
                    lambda dialog: dialog.accept()
                )

                target_element = None

                # 메인 페이지 탐색
                try:

                    el = new_tab.get_by_text(
                        "로그아웃"
                    ).first

                    if (
                        await el.count() > 0
                        and await el.is_visible()
                    ):

                        target_element = el

                except Exception:
                    pass

                # 프레임 탐색
                if not target_element:

                    for frame in new_tab.frames:

                        try:

                            el = frame.get_by_text(
                                "로그아웃"
                            ).first

                            if (
                                await el.count() > 0
                                and await el.is_visible()
                            ):

                                target_element = el

                                break

                        except Exception:
                            continue

                # 좌표 클릭
                if target_element:

                    box = await target_element.bounding_box()

                    if box:

                        center_x = (
                            box["x"]
                            + box["width"] / 2
                        )

                        center_y = (
                            box["y"]
                            + box["height"] / 2
                        )

                        await new_tab.mouse.move(
                            center_x,
                            center_y
                        )

                        await new_tab.mouse.click(
                            center_x,
                            center_y
                        )

                        print(
                            "로그아웃 클릭 성공"
                        )

                else:

                    await new_tab.mouse.click(
                        1150,
                        40
                    )

                    print(
                        "우측 상단 강제 클릭"
                    )

            except Exception as e:

                print("로그아웃 예외:", e)

            await asyncio.sleep(5)

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
