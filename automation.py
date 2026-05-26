import random
import time
import json
import os

# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright

def log(msg, type="info", **kwargs):
    data = {"type": type, "message": msg}
    data.update(kwargs)
    return json.dumps(data) + "\n"

def run_automation(username, password, temp_min, temp_max, start_row, end_row, time_period, show_browser=True, u_value='skip', speed='normal', state=None):
    if state is None:
        state = {"should_stop": False, "paused": False}
        
    if speed == 'slow':
        wait_short = 600
        wait_med = 1000
        wait_long = 2500
    elif speed == 'fast':
        wait_short = 50
        wait_med = 150
        wait_long = 800
    else:
        wait_short = 200
        wait_med = 500
        wait_long = 1500
        
    total_to_process = end_row - start_row + 1
    
    if os.environ.get('RENDER') == 'true':
        show_browser = False

    with sync_playwright() as p:
        yield log("กำลังเปิดเบราว์เซอร์...")
        browser = p.chromium.launch(headless=not show_browser)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        page.on("dialog", lambda dialog: dialog.accept())
        
        try:
            # === Login ===
            yield log("กำลังเข้าสู่หน้าล็อกอิน...")
            page.goto("https://rtamed.rta.mi.th:8443/login")
            page.wait_for_selector('input')
            
            if state.get("should_stop"): return
                
            inputs = page.locator('input').all()
            if len(inputs) >= 2:
                inputs[0].fill(username)
                inputs[1].fill(password)
                yield log("กรอกชื่อผู้ใช้และรหัสผ่านเรียบร้อย")
            else:
                yield log("ไม่พบช่องกรอกชื่อผู้ใช้และรหัสผ่าน", "error")
                return
            
            yield log("กำลังกดเข้าสู่ระบบ...")
            page.locator('button').click()
            page.wait_for_timeout(3000)
            
            if state.get("should_stop"): return
                
            # === Navigation ===
            yield log("กำลังไปยังเมนู 'การคัดกรอง'...")
            page.get_by_text("การคัดกรอง").click()
            page.wait_for_timeout(wait_long)
            
            # Close Notification if present
            try:
                close_btn = page.locator(".toast-close-button, .close, button.close, .btn-close, [aria-label='Close'], :text-is('×'), :text-is('x')").first
                if close_btn.is_visible(timeout=2000):
                    close_btn.click()
                    yield log("ปิดหน้าต่างแจ้งเตือนอัตโนมัติแล้ว")
            except Exception:
                pass
            
            # === Processing Rows ===
            processed = 0
            yield log(f"เริ่มดำเนินการตั้งแต่ลำดับที่ {start_row} ถึง {end_row}")
            yield log("เตรียมความพร้อม...", type="progress", current=0, total=total_to_process)
            
            target_row = start_row
            
            while target_row <= end_row:
                if state.get("should_stop"):
                    yield log("ยกเลิกการทำงาน", "warning")
                    break
                    
                while state.get("paused"):
                    if state.get("should_stop"):
                        break
                    time.sleep(1)
                
                if state.get("should_stop"):
                    break
                    
                rows = page.locator('tbody tr').all()
                if not rows:
                    yield log("ไม่พบข้อมูลตารางในหน้านี้", "warning")
                    break
                    
                found_on_page = False
                
                for row_idx, row in enumerate(rows):
                    if target_row > end_row or state.get("should_stop"):
                        break
                        
                    while state.get("paused"):
                        time.sleep(1)
                        if state.get("should_stop"): break
                        
                    try:
                        first_col_text = row.locator('td').first.inner_text().strip()
                        row_num = int(first_col_text)
                    except Exception:
                        continue 
                        
                    if row_num == target_row:
                        target_temp = round(random.uniform(temp_min, temp_max), 1)
                        try:
                            time_offset = 1 if time_period == 'morning' else (2 if time_period == 'afternoon' else 3)
                            row.scroll_into_view_if_needed()
                            page.wait_for_timeout(wait_short)
                            
                            # === U Value ===
                            if u_value != 'skip':
                                u_cell = row.locator("td:text-is('U'), th:text-is('U')").first
                                if u_cell.count() == 0:
                                    u_cell = row.locator("td, th").filter(has_text="U").last
                                
                                if u_cell.count() > 0:
                                    u_sibling_cells = u_cell.locator("~ td, ~ th")
                                    if u_sibling_cells.count() >= time_offset:
                                        target_u_cell = u_sibling_cells.nth(time_offset - 1)
                                        target_u_cell.click(force=True)
                                        actual_u = str(random.randint(0, 4)) if u_value == 'random' else u_value
                                        page.wait_for_timeout(wait_med)
                                        u_popup = page.locator("ngb-popover-window, .popover").last
                                        if u_popup.is_visible():
                                            u_popup.get_by_text(actual_u, exact=True).click()
                                        page.wait_for_timeout(wait_short)
                            
                            # === T Value ===
                            next_row = page.locator('tbody tr').nth(row_idx + 1)
                            target_td = next_row.locator('td').nth(time_offset)
                            target_td.click()
                            
                            popup = page.locator("ngb-popover-window, .popover").last
                            popup.wait_for(state="visible", timeout=5000)
                            
                            popup.get_by_text(str(int(target_temp)), exact=True).click()
                            page.wait_for_timeout(wait_short)
                            
                            if popup.is_visible():
                                decimal_part = int(round((target_temp - int(target_temp)) * 10))
                                if decimal_part == 0:
                                    popup.get_by_text(str(int(target_temp)), exact=True).click(timeout=2000)
                                else:
                                    popup.get_by_text(f".{decimal_part}", exact=True).click(timeout=2000)
                                    
                        except Exception as e:
                            yield log(f"เกิดข้อผิดพลาดในการคลิกอุณหภูมิลำดับที่ {row_num}: {str(e)}", "warning")
                        
                        processed += 1
                        yield log(f"[{processed}] กรอกอุณหภูมิ {target_temp} สำหรับลำดับที่ {row_num} เรียบร้อย", type="progress", current=processed, total=total_to_process)
                        page.wait_for_timeout(wait_med)
                        
                        target_row += 1
                        found_on_page = True
                
                if state.get("should_stop"):
                    break
                
                # === Save Page ===
                if found_on_page:
                    yield log("กำลังค้นหาปุ่มบันทึกข้อมูลสำหรับหน้านี้...")
                    try:
                        save_btn = page.locator("button:has-text('บันทึก')")
                        if save_btn.count() == 0:
                            save_btn = page.locator(":text-matches('บันทึก')").last
                        
                        if save_btn.count() > 0:
                            save_btn.first.click()
                            page.wait_for_timeout(wait_long)
                            
                            confirm_btn = page.locator("ngb-modal-window button:has-text('ตกลง')")
                            if confirm_btn.count() == 0:
                                confirm_btn = page.locator("button:has-text('ตกลง')").last
                            if confirm_btn.count() > 0 and confirm_btn.first.is_visible():
                                confirm_btn.first.click()
                                
                            page.wait_for_timeout(wait_med)
                            success_btn = page.locator("ngb-modal-window button:has-text('ตกลง')")
                            if success_btn.count() == 0:
                                success_btn = page.locator("button:has-text('ตกลง')").last
                            if success_btn.count() > 0 and success_btn.first.is_visible():
                                success_btn.first.click()
                                
                            page.wait_for_timeout(wait_long)
                    except Exception:
                        pass
                        
                # === Pagination ===
                if target_row <= end_row:
                    yield log("กำลังเปลี่ยนไปยังหน้าถัดไป...")
                    try:
                        next_page_number = page.locator(".pagination .active + li a, .pagination .active + .page-item .page-link").first
                        if next_page_number.count() > 0:
                            next_page_number.click()
                            page.wait_for_timeout(wait_long)
                        else:
                            next_btn = page.locator("a:has-text('›'), a:has-text('Next'), a:has-text('ถัดไป'), [aria-label='Next'], [aria-label='ถัดไป']")
                            if next_btn.count() > 0:
                                next_btn.first.click()
                                page.wait_for_timeout(wait_long)
                            else:
                                break
                    except Exception:
                        break

            if not state.get("should_stop"):
                yield log(f"ทำงานเสร็จสิ้นทั้งหมด {processed} รายการ!", "success", current=processed, total=total_to_process)

        except Exception as e:
            yield log(f"เกิดข้อผิดพลาด: {str(e)}", "error")
        finally:
            browser.close()
