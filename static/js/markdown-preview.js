(function () {
    'use strict';

    var THEMES = ['github', 'clean', 'wechat'];
    var STORAGE_KEY = 'markdown-preview-theme';

    function storageGet(fallback) {
        try {
            return localStorage.getItem(STORAGE_KEY) || fallback;
        } catch (error) {
            return fallback;
        }
    }

    function storageSet(value) {
        try {
            localStorage.setItem(STORAGE_KEY, value);
        } catch (error) {
            // Preview preferences remain optional when storage is unavailable.
        }
    }

    function normalizeTheme(theme) {
        return THEMES.indexOf(theme) >= 0 ? theme : 'github';
    }

    function refreshDiagrams(root) {
        if (typeof window.renderMarkdownMermaid !== 'function') return;
        var target = root.querySelector('.markdown-body');
        if (!target || !target.querySelector('.mermaid')) return;
        window.renderMarkdownMermaid(target);
    }

    function applyTheme(root, theme, persist) {
        theme = normalizeTheme(theme);
        THEMES.forEach(function (name) {
            root.classList.toggle('preview-theme-' + name, name === theme);
        });
        var select = root.querySelector('[data-markdown-preview-theme]');
        if (select) select.value = theme;
        if (persist) {
            storageSet(theme);
            refreshDiagrams(root);
        }
    }

    function init(root) {
        if (!root || root.dataset.previewInitialized === 'true') return;
        root.dataset.previewInitialized = 'true';
        var select = root.querySelector('[data-markdown-preview-theme]');
        if (!select) return;

        applyTheme(root, storageGet(root.dataset.defaultPreviewTheme || 'github'), false);
        select.addEventListener('change', function () {
            applyTheme(root, select.value, true);
        });
    }

    function initAll(scope) {
        scope = scope || document;
        if (scope.matches && scope.matches('[data-markdown-preview-shell]')) init(scope);
        if (!scope.querySelectorAll) return;
        scope.querySelectorAll('[data-markdown-preview-shell]').forEach(init);
    }

    window.DjangoDiskMarkdownPreview = {
        applyTheme: applyTheme,
        init: init,
        initAll: initAll
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initAll(document); });
    } else {
        initAll(document);
    }
    document.addEventListener('htmx:afterSwap', function (event) {
        initAll(event.detail && event.detail.target ? event.detail.target : document);
    });
})();
