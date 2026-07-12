(function () {
    'use strict';

    function storageGet(key, fallback) {
        try {
            return localStorage.getItem(key) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function storageSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (error) {
            // Preferences are optional when storage is unavailable.
        }
    }

    function init(root) {
        if (root.dataset.initialized === 'true') return;
        root.dataset.initialized = 'true';

        var editor = root.querySelector('[data-markdown-source]');
        var preview = root.querySelector('[data-markdown-preview]');
        var previewPane = root.querySelector('[data-preview-pane]');
        var statusBar = root.querySelector('[data-render-status]');
        var wordCount = root.querySelector('[data-word-count]');
        var form = root.querySelector('[data-markdown-form]');
        var contentInput = root.querySelector('[data-content-input]');
        var toolbar = root.querySelector('[data-format-toolbar]');
        var themeSelect = root.querySelector('[data-preview-theme]');
        var syncToggle = root.querySelector('[data-scroll-sync]');
        var imageInput = root.querySelector('[data-image-input]');
        var renderTimer = null;
        var syncing = false;

        function setStatus(message) {
            if (statusBar) statusBar.textContent = message;
        }

        function updateCount() {
            if (!wordCount) return;
            var value = editor.value;
            var chars = value.length;
            var lines = value.split(/\n/).length;
            wordCount.textContent = chars + ' 字 / ' + lines + ' 行';
        }

        function render() {
            if (!window.DjangoDiskMarkdownRenderer) {
                setStatus('渲染组件加载失败');
                return;
            }
            setStatus('渲染中...');
            try {
                window.DjangoDiskMarkdownRenderer.render(editor.value, preview);
                setStatus('就绪');
            } catch (error) {
                setStatus('渲染失败');
                preview.textContent = 'Markdown 渲染失败: ' + error.message;
            }
        }

        function queueRender() {
            clearTimeout(renderTimer);
            setStatus('等待输入...');
            renderTimer = setTimeout(render, 120);
        }

        function notifyChange() {
            updateCount();
            queueRender();
        }

        function replaceSelection(before, after, placeholder) {
            var start = editor.selectionStart;
            var end = editor.selectionEnd;
            var selected = editor.value.substring(start, end) || placeholder || '';
            editor.setRangeText(before + selected + after, start, end, 'end');
            if (!placeholder && start === end) {
                editor.setSelectionRange(start + before.length, start + before.length);
            }
            editor.focus();
            notifyChange();
        }

        function prefixLines(prefix) {
            var start = editor.selectionStart;
            var end = editor.selectionEnd;
            var value = editor.value;
            var lineStart = value.lastIndexOf('\n', start - 1) + 1;
            var lineEnd = value.indexOf('\n', end);
            if (lineEnd === -1) lineEnd = value.length;
            var selected = value.substring(lineStart, lineEnd);
            var replacement = selected.split('\n').map(function (line) {
                return prefix + line;
            }).join('\n');
            editor.setRangeText(replacement, lineStart, lineEnd, 'select');
            editor.focus();
            notifyChange();
        }

        function insertText(text) {
            var start = editor.selectionStart;
            editor.setRangeText(text, start, editor.selectionEnd, 'end');
            editor.focus();
            notifyChange();
        }

        function applyViewMode(mode) {
            if (!['edit', 'split', 'preview'].includes(mode)) mode = 'split';
            root.classList.remove('view-edit', 'view-split', 'view-preview');
            root.classList.add('view-' + mode);
            root.querySelectorAll('[data-view-mode]').forEach(function (button) {
                var active = button.dataset.viewMode === mode;
                button.classList.toggle('active', active);
                button.setAttribute('aria-pressed', active ? 'true' : 'false');
            });
            storageSet('markdown-view-mode', mode);
        }

        function applyTheme(theme) {
            if (!['github', 'clean', 'wechat'].includes(theme)) theme = 'github';
            root.classList.remove('preview-theme-github', 'preview-theme-clean', 'preview-theme-wechat');
            root.classList.add('preview-theme-' + theme);
            if (themeSelect) themeSelect.value = theme;
            storageSet('markdown-preview-theme', theme);
        }

        function copyRenderedHtml() {
            var html = preview.innerHTML;
            var plain = preview.innerText;
            var copied;
            if (navigator.clipboard && window.ClipboardItem) {
                copied = navigator.clipboard.write([new ClipboardItem({
                    'text/html': new Blob([html], { type: 'text/html' }),
                    'text/plain': new Blob([plain], { type: 'text/plain' })
                })]);
            } else if (navigator.clipboard) {
                copied = navigator.clipboard.writeText(html);
            } else {
                var helper = document.createElement('textarea');
                helper.value = html;
                helper.style.position = 'fixed';
                helper.style.opacity = '0';
                document.body.appendChild(helper);
                helper.select();
                copied = Promise.resolve(document.execCommand('copy'));
                helper.remove();
            }
            Promise.resolve(copied).then(function () {
                setStatus('已复制渲染 HTML');
                setTimeout(function () { setStatus('就绪'); }, 1500);
            }).catch(function () {
                setStatus('复制失败');
            });
        }

        function syncScroll(source, target) {
            if (!syncToggle || !syncToggle.checked || syncing) return;
            var sourceRange = source.scrollHeight - source.clientHeight;
            var targetRange = target.scrollHeight - target.clientHeight;
            if (sourceRange <= 0 || targetRange <= 0) return;
            syncing = true;
            target.scrollTop = (source.scrollTop / sourceRange) * targetRange;
            requestAnimationFrame(function () { syncing = false; });
        }

        editor.addEventListener('input', notifyChange);
        editor.addEventListener('scroll', function () { syncScroll(editor, previewPane); });
        previewPane.addEventListener('scroll', function () { syncScroll(previewPane, editor); });

        if (form) {
            form.addEventListener('submit', function () {
                contentInput.value = editor.value;
            });
        }

        if (toolbar) {
            toolbar.addEventListener('click', function (event) {
                var button = event.target.closest('button[data-action]');
                if (!button) return;
                var action = button.dataset.action;
                if (action === 'bold') replaceSelection('**', '**', '粗体');
                else if (action === 'italic') replaceSelection('_', '_', '斜体');
                else if (action === 'strikethrough') replaceSelection('~~', '~~', '删除线');
                else if (action === 'heading') prefixLines('## ');
                else if (action === 'quote') prefixLines('> ');
                else if (action === 'ul') prefixLines('- ');
                else if (action === 'ol') prefixLines('1. ');
                else if (action === 'task') prefixLines('- [ ] ');
                else if (action === 'link') replaceSelection('[', '](url)', '链接文本');
                else if (action === 'image' && imageInput) imageInput.click();
                else if (action === 'image') replaceSelection('![', '](url)', '图片描述');
                else if (action === 'code') replaceSelection('`', '`', 'code');
                else if (action === 'codeblock') replaceSelection('\n```\n', '\n```\n', '代码');
                else if (action === 'table') insertText('\n| 列1 | 列2 | 列3 |\n| --- | --- | --- |\n| 内容 | 内容 | 内容 |\n');
                else if (action === 'hr') insertText('\n---\n');
            });
        }

        root.querySelectorAll('[data-view-mode]').forEach(function (button) {
            button.addEventListener('click', function () { applyViewMode(button.dataset.viewMode); });
        });
        root.querySelector('[data-copy-html]').addEventListener('click', copyRenderedHtml);
        themeSelect.addEventListener('change', function () { applyTheme(themeSelect.value); });
        syncToggle.addEventListener('change', function () {
            storageSet('markdown-scroll-sync', syncToggle.checked ? 'on' : 'off');
        });

        editor.addEventListener('keydown', function (event) {
            if (event.ctrlKey || event.metaKey) {
                var key = event.key.toLowerCase();
                if (key === 'b') { event.preventDefault(); replaceSelection('**', '**', '粗体'); }
                else if (key === 'i') { event.preventDefault(); replaceSelection('_', '_', '斜体'); }
                else if (key === 'k') { event.preventDefault(); replaceSelection('[', '](url)', '链接文本'); }
                else if (key === 's') { event.preventDefault(); form.requestSubmit(); }
            }
            if (event.key === 'Tab' && !event.ctrlKey && !event.metaKey) {
                event.preventDefault();
                if (editor.selectionStart === editor.selectionEnd) insertText('    ');
                else prefixLines('    ');
            }
        });

        if (imageInput && root.dataset.imageUploadUrl) {
            imageInput.addEventListener('change', function () {
                var file = imageInput.files[0];
                if (!file) return;
                var csrf = form.querySelector('[name=csrfmiddlewaretoken]');
                var formData = new FormData();
                formData.append('file', file);
                formData.append('folder_path', root.dataset.folderPath || '');
                setStatus('上传图片中...');
                fetch(root.dataset.imageUploadUrl, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': csrf.value },
                    body: formData
                }).then(function (response) {
                    return response.json();
                }).then(function (data) {
                    if (data.error) throw new Error(data.error);
                    insertText('![' + (data.filename || '图片') + '](' + data.url + ')');
                    if (window.showToast) showToast('图片已上传并插入', 'success');
                }).catch(function (error) {
                    setStatus('上传失败');
                    if (window.showToast) showToast('上传失败: ' + error.message, 'error');
                }).finally(function () {
                    imageInput.value = '';
                });
            });
        }

        var initialTheme = storageGet('markdown-preview-theme', 'github');
        var initialMode = storageGet('markdown-view-mode', 'split');
        syncToggle.checked = storageGet('markdown-scroll-sync', 'on') !== 'off';
        applyTheme(initialTheme);
        applyViewMode(initialMode);
        updateCount();
        render();
    }

    window.DjangoDiskMarkdownEditor = {
        init: init
    };

    document.querySelectorAll('[data-markdown-editor]').forEach(init);
})();
