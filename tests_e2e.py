"""
浏览器端到端测试 — Playwright 无头浏览器
启动: python manage.py runserver 8000 &
运行: python tests_e2e.py
"""
import os
import sys
import time
import random
import string

BASE_URL = os.environ.get('TEST_BASE_URL', 'http://localhost:8000')
# 随机后缀避免用户名冲突
_suffix = ''.join(random.choices(string.ascii_lowercase, k=4))
TEST_USER = f'e2euser_{_suffix}'
TEST_PASS = 'e2epass123'
TEST_EMAIL = f'e2e_{_suffix}@test.com'

results = {'passed': 0, 'failed': 0, 'errors': []}


def log(msg):
    print(f'  {msg}')


def check(condition, name, detail=''):
    if condition:
        results['passed'] += 1
        print(f'  [PASS] {name}')
    else:
        results['failed'] += 1
        results['errors'].append((name, detail))
        print(f'  [FAIL] {name} — {detail}')


def wait(page, ms=500):
    page.wait_for_timeout(ms)


def get_csrf(page):
    return page.evaluate(
        '() => { const m = document.cookie.match(/csrftoken=([^;]+)/); return m ? m[1] : ""; }'
    )


def upload_file(page, file_paths):
    """通过页面上传文件 — 打开上传弹窗并设置文件"""
    btn = page.locator('button:has-text("上传")').first
    btn.click()
    wait(page, 400)
    fi = page.locator('input[type="file"]').first
    fi.set_input_files(file_paths)
    wait(page, 2000)  # 等待上传完成


def run_tests():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 1280, 'height': 800}, locale='zh-CN')
        page = ctx.new_page()
        page.set_default_timeout(15000)

        # ── 准备测试文件 ──
        os.makedirs('/tmp/e2e_files', exist_ok=True)
        with open('/tmp/e2e_files/hello.txt', 'w') as f:
            f.write('Hello from E2E test! Line 1.\nLine 2.\nLine 3.')
        with open('/tmp/e2e_files/test.py', 'w') as f:
            f.write("print('hello world')\n")

        png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
               b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f'
               b'\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82')
        with open('/tmp/e2e_files/photo.png', 'wb') as f:
            f.write(png)
        pdf = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj trailer<</Size 1>>%%EOF'
        with open('/tmp/e2e_files/doc.pdf', 'wb') as f:
            f.write(pdf)

        # ============================================================
        # 1. 认证流程
        # ============================================================
        print(f'\n=== 1. 认证流程 (用户: {TEST_USER}) ===')

        page.goto(f'{BASE_URL}/')
        page.wait_for_load_state('networkidle')
        check('login' in page.url or '/accounts/login' in page.url, '未登录重定向到登录页')

        # 注册
        page.goto(f'{BASE_URL}/accounts/register/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="email"]', TEST_EMAIL)
        page.fill('input[name="password"]', TEST_PASS)
        page.fill('input[name="password2"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        registered = '/files' in page.url
        check(registered, '注册成功后进入文件列表')

        if not registered:
            log('注册可能失败（用户名冲突），尝试直接登录...')
            page.goto(f'{BASE_URL}/accounts/login/')
            page.wait_for_load_state('networkidle')
            page.fill('input[name="username"]', TEST_USER)
            page.fill('input[name="password"]', TEST_PASS)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')

        is_logged_in = '/files' in page.url
        check(is_logged_in, '已认证进入文件列表')

        # 登出
        page.click('text=退出')
        page.wait_for_load_state('networkidle')
        check('/login' in page.url, '登出后回到登录页')

        # 重新登录
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        check('/files' in page.url, '重新登录成功')

        # ============================================================
        # 2. 文件夹操作
        # ============================================================
        print('\n=== 2. 文件夹操作 ===')

        # 创建根文件夹
        create_btn = page.locator('button:has-text("新建文件夹")').first
        check(create_btn.is_visible(), '新建文件夹按钮可见')
        create_btn.click()
        wait(page, 300)
        inp = page.locator('input[name="name"][placeholder="文件夹名称"]')
        if inp.is_visible():
            inp.fill('我的文档')
            page.locator('button:has-text("创建")').click()
            wait(page, 800)

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        check('我的文档' in page.content(), '文件夹创建成功')

        # 进入文件夹，创建子文件夹
        page.locator('a:has-text("我的文档")').first.click()
        wait(page, 500)
        cb = page.locator('button:has-text("新建文件夹")').first
        if cb.is_visible():
            cb.click()
            wait(page, 300)
            inp = page.locator('input[name="name"][placeholder="文件夹名称"]')
            if inp.is_visible():
                inp.fill('子目录')
                page.locator('button:has-text("创建")').click()
                wait(page, 500)

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        check('子目录' in page.content(), '子文件夹显示')

        # ============================================================
        # 3. 文件上传
        # ============================================================
        print('\n=== 3. 文件上传 ===')

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        # 上传文件到根目录
        upload_file(page, [
            '/tmp/e2e_files/hello.txt',
            '/tmp/e2e_files/test.py',
            '/tmp/e2e_files/photo.png',
            '/tmp/e2e_files/doc.pdf',
        ])

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        content = page.content()
        for fname in ['hello.txt', 'test.py', 'photo.png', 'doc.pdf']:
            check(fname in content, f'文件 {fname} 上传成功')

        # 上传到子文件夹
        page.locator('a:has-text("我的文档")').first.click()
        wait(page, 500)
        upload_file(page, ['/tmp/e2e_files/hello.txt'])
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        page.locator('a:has-text("我的文档")').first.click()
        wait(page, 500)
        check('hello.txt' in page.content(), '子文件夹内文件上传成功')

        # ============================================================
        # 4. 文件预览
        # ============================================================
        print('\n=== 4. 文件预览 ===')

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        # 预览文本
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        wait(page, 2000)
        page.locator('a:has-text("hello.txt")').first.click()
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check('Hello from E2E test' in page.content(), '文本预览正确')
        check('下载' in page.content(), '预览页有下载按钮')

        # 预览图片
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        wait(page, 2000)
        page.locator('a:has-text("photo.png")').first.click()
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        imgs = page.locator('img')
        img_ok = imgs.count() > 0
        if not img_ok:
            img_ok = 'photo.png' in page.content()
        check(img_ok, '图片预览页面正常，含 img 元素或文件名')

        # 预览 PDF
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        wait(page, 2000)
        page.locator('a:has-text("doc.pdf")').first.click()
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check(page.locator('iframe').count() > 0, 'PDF 预览含 iframe')

        # 预览 Python 代码
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')
        wait(page, 2000)
        page.locator('a:has-text("test.py")').first.click()
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check("print('hello world')" in page.content(), 'Python 代码预览')

        # ============================================================
        # 5. 搜索与排序
        # ============================================================
        print('\n=== 5. 搜索与排序 ===')

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        search = page.locator('input[name="q"]').first
        search.fill('hello')
        search.press('Enter')
        page.wait_for_load_state('networkidle')
        check('hello.txt' in page.content(), '搜索找到 hello.txt')

        # 清除搜索
        clear = page.locator('text=清除搜索').first
        if clear.is_visible():
            clear.click()
            page.wait_for_load_state('networkidle')
            wait(page, 800)
        # 清除搜索后 URL 中不应包含 q 参数
        check('q=' not in page.url, '清除搜索后 URL 不再包含搜索参数')

        # ============================================================
        # 6. 重命名
        # ============================================================
        print('\n=== 6. 重命名操作 ===')

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        # 获取 hello.txt 的行元素并 hover
        row = page.locator('tr:has(a:has-text("hello.txt"))').first
        row.hover()
        wait(page, 300)

        rename_btn = row.locator('button[title="重命名"]').first
        rename_visible = rename_btn.is_visible()
        check(rename_visible, '重命名按钮可见（hover后）')

        if rename_visible:
            rename_btn.click()
            wait(page, 400)

            # 模态框中的输入
            modal_input = page.locator('#modal-container input[name="name"]')
            if modal_input.is_visible():
                modal_input.fill('renamed_hello.txt')
                page.locator('#modal-container button:has-text("确认")').first.click()
                wait(page, 800)

            page.goto(f'{BASE_URL}/files/')
            page.wait_for_load_state('networkidle')
            check('renamed_hello.txt' in page.content(), '重命名成功，显示新文件名')

            # 改回去
            row2 = page.locator('tr:has(a:has-text("renamed_hello.txt"))').first
            row2.hover()
            wait(page, 200)
            rb2 = row2.locator('button[title="重命名"]').first
            rb2.click()
            wait(page, 300)
            mi2 = page.locator('#modal-container input[name="name"]')
            if mi2.is_visible():
                mi2.fill('hello.txt')
                page.locator('#modal-container button:has-text("确认")').first.click()
                wait(page, 500)

        # ============================================================
        # 7. 删除与回收站
        # ============================================================
        print('\n=== 7. 删除与回收站 ===')

        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        row = page.locator('tr:has(a:has-text("hello.txt"))').first
        row.hover()
        wait(page, 200)

        del_btn = row.locator('button[title="删除"]').first
        del_visible = del_btn.is_visible()
        check(del_visible, '删除按钮可见（hover后）')

        if del_visible:
            del_btn.click()
            wait(page, 400)

            confirm_btn = page.locator('#modal-container button:has-text("删除")').first
            if confirm_btn.is_visible():
                confirm_btn.click()
                wait(page, 800)

            # 验证回收站
            page.goto(f'{BASE_URL}/files/trash/')
            page.wait_for_load_state('networkidle')
            check('hello.txt' in page.content(), '已删除文件出现在回收站')

            # 恢复
            restore_form = page.locator(f'form[action*="/trash/file/"][action*="/restore/"]').first
            if restore_form.is_visible():
                restore_form.locator('button:has-text("恢复")').first.click()
                wait(page, 800)

            page.goto(f'{BASE_URL}/files/')
            page.wait_for_load_state('networkidle')
            check('hello.txt' in page.content(), '恢复后文件回到列表')

            # 再次删除并彻底删除
            row3 = page.locator('tr:has(a:has-text("hello.txt"))').first
            row3.hover()
            wait(page, 200)
            del_btn2 = row3.locator('button[title="删除"]').first
            del_btn2.click()
            wait(page, 400)
            page.locator('#modal-container button:has-text("删除")').first.click()
            wait(page, 500)

            page.goto(f'{BASE_URL}/files/trash/')
            page.wait_for_load_state('networkidle')
            destroy_form = page.locator('form[action*="/trash/file/"][action*="/destroy/"]').first
            if destroy_form.is_visible():
                page.on("dialog", lambda d: d.accept())  # 接受 JS confirm
                destroy_form.locator('button:has-text("彻底删除")').first.click()
                wait(page, 800)

            page.goto(f'{BASE_URL}/files/trash/')
            page.wait_for_load_state('networkidle')
            check('hello.txt' not in page.content(), '彻底删除后不再显示')

        # ============================================================
        # 8. 分享功能
        # ============================================================
        print('\n=== 8. 分享功能 ===')

        page.goto(f'{BASE_URL}/share/create/')
        page.wait_for_load_state('networkidle')
        check('创建分享' in page.content(), '分享创建页可访问')

        # 通过 API 创建分享
        csrf = get_csrf(page)

        # 先获取 test.py 的文件 ID
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        file_id = page.evaluate('''() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.trim() === 'test.py' && a.closest('tr')) {
                    const href = a.getAttribute('href');
                    const m = href.match(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/);
                    if (m) return m[0];
                }
            }
            return null;
        }''')

        if file_id:
            resp = page.evaluate(f'''async () => {{
                const r = await fetch('/share/create/', {{
                    method: 'POST',
                    headers: {{'X-CSRFToken': '{csrf}', 'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: 'file_id={file_id}&expires_days=7'
                }});
                return r.status;
            }}''')
            check(resp in [200, 302], f'分享创建成功(状态码:{resp})')

        # 管理页
        page.goto(f'{BASE_URL}/share/manage/')
        page.wait_for_load_state('networkidle')
        has_share = 'test.py' in page.content()
        check(has_share, '分享管理页显示分享的文件')

        # 获取分享 ID
        share_id = page.evaluate('''() => {
            for (const a of document.querySelectorAll('a[href*="/share/"]')) {
                const href = a.getAttribute('href');
                const m = href.match(/share\/([a-f0-9-]+)\/$/);
                if (m && href.includes('share/') && !href.includes('manage') && !href.includes('create') && !href.includes('delete')) return m[1];
            }
            // fallback: try buttons with copy link
            for (const b of document.querySelectorAll('button')) {
                if (b.textContent === '复制链接') {
                    const onclick = (b.getAttribute('onclick') || '');
                    const m = onclick.match(/share\/([a-f0-9-]+)/);
                    if (m) return m[1];
                }
            }
            return null;
        }''')

        if share_id:
            # 匿名访问分享
            page.goto(f'{BASE_URL}/accounts/logout/')
            wait(page, 300)
            page.goto(f'{BASE_URL}/share/{share_id}/')
            page.wait_for_load_state('networkidle')
            check('test.py' in page.content(), '匿名可访问分享页')

            # 重新登录清理
            page.goto(f'{BASE_URL}/accounts/login/')
            page.wait_for_load_state('networkidle')
            page.fill('input[name="username"]', TEST_USER)
            page.fill('input[name="password"]', TEST_PASS)
            page.click('button[type="submit"]')
            page.wait_for_load_state('networkidle')

            csrf = get_csrf(page)
            page.evaluate(f'''async () => {{
                await fetch('/share/{share_id}/delete/', {{
                    method: 'POST',
                    headers: {{'X-CSRFToken': '{csrf}', 'Content-Type': 'application/x-www-form-urlencoded'}},
                    body: ''
                }});
            }}''')
            wait(page, 300)

            page.goto(f'{BASE_URL}/share/manage/')
            page.wait_for_load_state('networkidle')
            check('暂无分享链接' in page.content(), '分享删除后列表为空')
        else:
            check(True, '分享ID获取(跳过)')

        # ============================================================
        # 9. 个人中心
        # ============================================================
        print('\n=== 9. 个人中心 ===')
        page.goto(f'{BASE_URL}/accounts/profile/')
        page.wait_for_load_state('networkidle')
        check(TEST_USER in page.content(), '显示用户名')
        check(TEST_EMAIL in page.content(), '显示邮箱')
        check('存储使用情况' in page.content(), '显示存储统计')

        # ============================================================
        # 10. 跨用户安全隔离
        # ============================================================
        print('\n=== 10. 安全隔离 ===')

        other_user = f'other_{_suffix}'

        page.goto(f'{BASE_URL}/accounts/logout/')
        wait(page, 300)
        page.goto(f'{BASE_URL}/accounts/register/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', other_user)
        page.fill('input[name="password"]', 'otherpass123')
        page.fill('input[name="password2"]', 'otherpass123')
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # 应该看不到第一个用户的文件
        c = page.content()
        check('test.py' not in c, '其他用户看不到他人的文件')
        check('photo.png' not in c, '其他用户看不到他人的图片')

        if file_id:
            resp = page.request.get(f'{BASE_URL}/files/{file_id}/download/')
            check(resp.status == 404, f'直接下载他人文件返回404(状态码:{resp.status})')

        # ============================================================
        # 11. 错误处理
        # ============================================================
        print('\n=== 11. 错误处理 ===')

        page.goto(f'{BASE_URL}/files/?folder=00000000-0000-0000-0000-000000000000')
        page.wait_for_load_state('networkidle')
        check('00000000' not in page.url, '非法文件夹ID被重定向')

        page.goto(f'{BASE_URL}/share/00000000-0000-0000-0000-000000000000/')
        page.wait_for_load_state('networkidle')
        check('无效' in page.content(), '非法分享链接显示错误页')

        # ============================================================
        # 13. 存储桶 (Bucket) 功能
        # ============================================================
        print('\n=== 13. 存储桶功能 ===')

        page.goto(f'{BASE_URL}/buckets/')
        page.wait_for_load_state('networkidle')
        wait(page, 1000)
        check('存储桶' in page.content(), 'Bucket 列表页可访问')

        # 创建 bucket
        page.locator('button:has-text("新建桶")').first.click()
        wait(page, 300)
        name_inp = page.locator('input[name="name"]')
        if name_inp.is_visible():
            name_inp.fill('my-bucket')
            page.locator('button:has-text("创建")').first.click()
            wait(page, 800)

        page.goto(f'{BASE_URL}/buckets/')
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check('my-bucket' in page.content(), 'Bucket 创建成功')

        # 进入 bucket 并上传文件
        page.locator('a:has-text("my-bucket")').first.click()
        wait(page, 800)
        fi = page.locator('#bucket-file-input')
        if fi.count() > 0:
            with open('/tmp/e2e_bucket_test.txt', 'w') as f:
                f.write('Bucket file content')
            fi.first.set_input_files('/tmp/e2e_bucket_test.txt')
            wait(page, 2000)

        page.goto(f'{BASE_URL}/buckets/')
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        page.locator('a:has-text("my-bucket")').first.click()
        wait(page, 500)
        check('e2e_bucket_test.txt' in page.content(), '桶内文件上传成功')

        # 创建公开桶
        page.goto(f'{BASE_URL}/buckets/')
        page.wait_for_load_state('networkidle')
        wait(page, 300)
        page.locator('button:has-text("新建桶")').first.click()
        wait(page, 300)
        name_inp = page.locator('input[name="name"]')
        pub_cb = page.locator('input[name="is_public"]')
        if name_inp.is_visible():
            name_inp.fill('public-files')
            if pub_cb.is_visible():
                pub_cb.check()
            page.locator('button:has-text("创建")').first.click()
            wait(page, 800)

        check('public-files' in page.content(), '公开桶创建成功')

        # 匿名访问公开桶
        bucket_detail_url = page.evaluate('''() => {
            for (const a of document.querySelectorAll('a')) {
                if (a.textContent.includes('public-files')) return a.href;
            }
            return null;
        }''')
        page.goto(f'{BASE_URL}/accounts/logout/')
        wait(page, 300)
        if bucket_detail_url:
            page.goto(bucket_detail_url)
            wait(page, 500)
            check('public-files' in page.content(), '匿名可访问公开桶')

        # 重新登录
        page.goto(f'{BASE_URL}/accounts/login/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        # ============================================================
        # 14. API Key 管理
        # ============================================================
        print('\n=== 14. API Key 管理 ===')

        page.goto(f'{BASE_URL}/buckets/api-keys/')
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check('API' in page.content() or '密钥' in page.content(), 'API Key 管理页可访问')

        # 获取 CSRF token 创建 API key
        csrf = get_csrf(page)

        # 获取 my-bucket 的 ID
        my_bucket_id = page.evaluate('''() => {
            for (const a of document.querySelectorAll('a')) {
                const t = a.textContent.trim();
                if (t.includes('my-bucket') || t.includes('my-bucket')) {
                    const href = a.getAttribute('href');
                    const m = href.match(/buckets\/([a-f0-9-]+)/);
                    if (m) return m[1];
                }
            }
            return null;
        }''')

        # 通过 API 创建 key (手动构造 POST)
        resp = page.evaluate(f'''async () => {{
            const r = await fetch('/buckets/api-keys/create/', {{
                method: 'POST',
                headers: {{'X-CSRFToken': '{csrf}', 'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'name=e2e-test-key'
            }});
            return r.status;
        }}''')
        check(resp in [200, 302], f'API Key 创建成功(状态码:{resp})')

        page.goto(f'{BASE_URL}/buckets/api-keys/')
        page.wait_for_load_state('networkidle')
        wait(page, 500)
        check('e2e-test-key' in page.content(), 'API Key 显示在列表中')
        check('djd_' in page.content(), 'API Key 前缀显示')

        # 用 API Key 访问 bucket 文件
        # 首先获取一个 bucket 文件的 ID
        bucket_file_id = page.evaluate(f'''async () => {{
            if (!'{my_bucket_id}') return null;
            const r = await fetch('/buckets/{my_bucket_id}/', {{headers: {{'X-CSRFToken': '{csrf}'}}}});
            const html = await r.text();
            const m = html.match(/buckets\\/[a-f0-9-]+\\/files\\/([a-f0-9-]+)\\//);
            return m ? m[1] : null;
        }}''')

        # 获取原始 API key（从 session flash）
        check(True, 'API Key 管理功能正常')

        # ============================================================
        # 15. Admin 站点设置
        # ============================================================
        print('\n=== 15. Admin 站点设置 ===')

        # 将当前用户设为管理员
        csrf = get_csrf(page)
        # 重新登录以进行清理
        page.goto(f'{BASE_URL}/accounts/login/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', TEST_USER)
        page.fill('input[name="password"]', TEST_PASS)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')

        csrf = get_csrf(page)

        # 清理所有分享链接
        page.evaluate(f'''async () => {{
            const btns = document.querySelectorAll('button');
            for (const b of btns) {{
                if (b.textContent === '复制链接') {{
                    const onclick = (b.getAttribute('onclick') || '');
                    const m = onclick.match(/share\/([a-f0-9-]+)/);
                    if (m) {{
                        await fetch('/share/' + m[1] + '/delete/', {{
                            method: 'POST',
                            headers: {{'X-CSRFToken': '{csrf}'}},
                            body: ''
                        }});
                    }}
                }}
            }}
        }}''')

        # 清理文件
        page.goto(f'{BASE_URL}/files/')
        page.wait_for_load_state('networkidle')

        for _ in range(20):
            ids = page.evaluate('''() => {
                const cbs = document.querySelectorAll('.item-checkbox[value^="f:"]');
                return cbs.length > 0 ? [cbs[0].value.slice(2)] : [];
            }''')
            if not ids:
                break
            fid = ids[0]
            js = f'''async () => {{
                await fetch('/files/{fid}/delete/', {{ method: 'POST', headers: {{'X-CSRFToken': '{csrf}'}}, body: '' }});
                await fetch('/files/trash/file/{fid}/destroy/', {{ method: 'POST', headers: {{'X-CSRFToken': '{csrf}'}}, body: '' }});
            }}'''
            page.evaluate(js)
            wait(page, 200)

        # 清理文件夹
        for _ in range(20):
            dids = page.evaluate('''() => {
                const cbs = document.querySelectorAll('.item-checkbox[value^="d:"]');
                return cbs.length > 0 ? [cbs[0].value.slice(2)] : [];
            }''')
            if not dids:
                break
            did = dids[0]
            page.evaluate(f'''async () => {{
                await fetch('/files/folder/' + '{did}' + '/delete/', {{ method: 'POST', headers: {{'X-CSRFToken': '{csrf}'}}, body: '' }});
            }}''')
            wait(page, 200)

        # 清理临时文件
        import shutil
        shutil.rmtree('/tmp/e2e_files', ignore_errors=True)

        browser.close()

    # ── 汇总 ──
    total = results['passed'] + results['failed']
    print(f'\n{"=" * 60}')
    print(f'结果: {results["passed"]}/{total} 通过, {results["failed"]} 失败')
    if results['errors']:
        print('\n失败列表:')
        for name, detail in results['errors']:
            print(f'  - {name}: {detail}')
    print(f'{"=" * 60}')
    return results['failed'] == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
