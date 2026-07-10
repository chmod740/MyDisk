(function () {
    'use strict';

    var ALLOWED_TAGS = new Set([
        'a', 'abbr', 'b', 'blockquote', 'br', 'code', 'del', 'details', 'div',
        'em', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'input',
        'kbd', 'li', 'mark', 'ol', 'p', 'pre', 's', 'samp', 'small', 'span',
        'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'tfoot',
        'th', 'thead', 'tr', 'u', 'ul', 'var',
        // KaTeX MathML output.
        'math', 'semantics', 'annotation', 'mrow', 'mi', 'mo', 'mn', 'mtext',
        'mspace', 'msup', 'msub', 'msubsup', 'mfrac', 'msqrt', 'mroot',
        'mover', 'munder', 'munderover', 'mtable', 'mtr', 'mtd', 'menclose',
        'mpadded', 'mstyle', 'mphantom'
    ]);
    var DROP_CONTENT_TAGS = new Set([
        'script', 'style', 'iframe', 'object', 'embed', 'svg', 'template',
        'textarea', 'title', 'noscript'
    ]);
    var GLOBAL_ATTRIBUTES = new Set([
        'class', 'title', 'role', 'dir', 'aria-hidden', 'aria-label'
    ]);
    var TAG_ATTRIBUTES = {
        a: new Set(['href', 'target', 'rel']),
        img: new Set(['src', 'alt', 'width', 'height', 'loading']),
        input: new Set(['type', 'checked', 'disabled']),
        ol: new Set(['start']),
        li: new Set(['value']),
        td: new Set(['colspan', 'rowspan', 'align']),
        th: new Set(['colspan', 'rowspan', 'align']),
        math: new Set(['display', 'xmlns']),
        annotation: new Set(['encoding'])
    };
    var SAFE_STYLE_PROPERTIES = new Set([
        'border-bottom-width', 'height', 'left', 'margin-left', 'margin-right',
        'min-width', 'padding-left', 'position', 'top', 'vertical-align', 'width'
    ]);

    function safeUrl(value, isImage) {
        var normalized = String(value || '').replace(/[\u0000-\u0020\u007f]+/g, '');
        if (!normalized) return false;
        if (normalized[0] === '#' || normalized[0] === '/' || normalized.indexOf('./') === 0 || normalized.indexOf('../') === 0) {
            return true;
        }
        if (/^https?:/i.test(normalized)) return true;
        if (!isImage && /^mailto:/i.test(normalized)) return true;
        return isImage && /^data:image\/(?:gif|jpe?g|png|webp);base64,/i.test(normalized);
    }

    function sanitizeStyle(value) {
        return String(value || '').split(';').map(function (declaration) {
            var separator = declaration.indexOf(':');
            if (separator < 1) return '';
            var property = declaration.slice(0, separator).trim().toLowerCase();
            var styleValue = declaration.slice(separator + 1).trim();
            if (!SAFE_STYLE_PROPERTIES.has(property)) return '';
            if (/url\s*\(|expression\s*\(|@import|javascript:/i.test(styleValue)) return '';
            return property + ':' + styleValue;
        }).filter(Boolean).join(';');
    }

    function sanitizeElement(element) {
        var tag = element.localName.toLowerCase();
        if (DROP_CONTENT_TAGS.has(tag)) {
            element.remove();
            return;
        }
        if (!ALLOWED_TAGS.has(tag)) {
            var parent = element.parentNode;
            if (!parent) return;
            while (element.firstChild) parent.insertBefore(element.firstChild, element);
            element.remove();
            return;
        }

        Array.from(element.attributes).forEach(function (attribute) {
            var name = attribute.name.toLowerCase();
            var allowedForTag = TAG_ATTRIBUTES[tag];
            var isAllowed = GLOBAL_ATTRIBUTES.has(name) || (allowedForTag && allowedForTag.has(name));
            if (name === 'style') {
                var cleanStyle = sanitizeStyle(attribute.value);
                if (cleanStyle) element.setAttribute('style', cleanStyle);
                else element.removeAttribute(attribute.name);
                return;
            }
            if (!isAllowed || name.indexOf('on') === 0) {
                element.removeAttribute(attribute.name);
                return;
            }
            if (name === 'href' && !safeUrl(attribute.value, false)) element.removeAttribute(attribute.name);
            if (name === 'src' && !safeUrl(attribute.value, tag === 'img')) element.removeAttribute(attribute.name);
        });

        if (tag === 'a' && element.getAttribute('target') === '_blank') {
            element.setAttribute('rel', 'noopener noreferrer');
        }
        if (tag === 'input') {
            if ((element.getAttribute('type') || '').toLowerCase() !== 'checkbox') {
                element.remove();
                return;
            }
            element.setAttribute('disabled', '');
        }
    }

    function sanitizeTree(root) {
        Array.from(root.children).forEach(function (element) {
            sanitizeTree(element);
            sanitizeElement(element);
        });
        return root;
    }

    window.sanitizeMarkdownHtml = function (html) {
        var documentFragment = new DOMParser().parseFromString(String(html || ''), 'text/html');
        return sanitizeTree(documentFragment.body);
    };

    window.setSanitizedMarkdownHtml = function (target, html) {
        if (!target) return;
        var sanitizedBody = window.sanitizeMarkdownHtml(html);
        var nodes = Array.from(sanitizedBody.childNodes).map(function (node) {
            return document.importNode(node, true);
        });
        target.replaceChildren.apply(target, nodes);
    };
})();
