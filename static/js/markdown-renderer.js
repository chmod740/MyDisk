(function () {
    'use strict';

    var ALERT_LABELS = {
        NOTE: '说明',
        TIP: '提示',
        IMPORTANT: '重要',
        WARNING: '警告',
        CAUTION: '注意'
    };
    var mermaidTimers = new WeakMap();

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function token(kind, index) {
        return '\uE000DD' + kind + index + '\uE001';
    }

    function dependenciesReady() {
        return typeof marked !== 'undefined'
            && typeof hljs !== 'undefined'
            && typeof katex !== 'undefined'
            && typeof window.setSanitizedMarkdownHtml === 'function';
    }

    function protectFencedCode(text, codeBlocks) {
        var lines = text.split('\n');
        var output = [];
        var index = 0;

        while (index < lines.length) {
            var opening = lines[index].match(/^ {0,3}(`{3,}|~{3,})[^\n]*$/);
            if (!opening) {
                output.push(lines[index]);
                index += 1;
                continue;
            }

            var fence = opening[1];
            var fenceCharacter = fence.charAt(0);
            var closing = new RegExp(
                '^ {0,3}' + (fenceCharacter === '`' ? '`' : '~')
                + '{' + fence.length + ',}[ \\t]*$'
            );
            var block = [lines[index]];
            index += 1;
            while (index < lines.length) {
                block.push(lines[index]);
                var isClosing = closing.test(lines[index]);
                index += 1;
                if (isClosing) break;
            }
            codeBlocks.push(block.join('\n'));
            output.push(token('CODE', codeBlocks.length - 1));
        }
        return output.join('\n');
    }

    function protectCode(text, codeBlocks) {
        text = protectFencedCode(text, codeBlocks);
        return text.replace(/(`+)([\s\S]*?)\1(?!`)/g, function (match) {
            codeBlocks.push(match);
            return token('CODE', codeBlocks.length - 1);
        });
    }

    function captureMath(text, mathBlocks, mathInlines) {
        text = text.replace(/\$\$([\s\S]*?)\$\$/g, function (_, formula) {
            mathBlocks.push(formula.trim());
            return token('MATHBLOCK', mathBlocks.length - 1);
        });
        text = text.replace(/\\\[([\s\S]*?)\\\]/g, function (_, formula) {
            mathBlocks.push(formula.trim());
            return token('MATHBLOCK', mathBlocks.length - 1);
        });
        text = text.replace(/\\\(([^\n]*?)\\\)/g, function (_, formula) {
            mathInlines.push(formula.trim());
            return token('MATHINLINE', mathInlines.length - 1);
        });
        return text.replace(/(^|[^\\$])\$(?!\$)([^\n$]*?\S)\$(?!\$)/g, function (match, prefix, formula) {
            if (!formula || /^\s/.test(formula)) return match;
            mathInlines.push(formula.trim());
            return prefix + token('MATHINLINE', mathInlines.length - 1);
        });
    }

    function restoreCode(text, codeBlocks) {
        codeBlocks.forEach(function (block, index) {
            text = text.split(token('CODE', index)).join(block);
        });
        return text;
    }

    function renderFormula(formula, displayMode) {
        try {
            return katex.renderToString(formula, {
                displayMode: displayMode,
                output: 'htmlAndMathml',
                strict: 'warn',
                throwOnError: false,
                trust: false
            });
        } catch (error) {
            return displayMode
                ? '<pre><code>' + escapeHtml(formula) + '</code></pre>'
                : '<code>' + escapeHtml(formula) + '</code>';
        }
    }

    function restoreMath(html, formulas, kind, displayMode) {
        formulas.forEach(function (formula, index) {
            var placeholder = token(kind, index);
            var rendered = renderFormula(formula, displayMode);
            if (displayMode) {
                html = html.split('<p>' + placeholder + '</p>').join(rendered);
            }
            html = html.split(placeholder).join(rendered);
        });
        return html;
    }

    function renderSource(source) {
        var text = String(source || '').replace(/\r\n?/g, '\n');
        var codeBlocks = [];
        var mathBlocks = [];
        var mathInlines = [];

        text = protectCode(text, codeBlocks);
        text = captureMath(text, mathBlocks, mathInlines);
        text = restoreCode(text, codeBlocks);

        marked.setOptions({
            gfm: true,
            breaks: true,
            pedantic: false
        });

        var html = marked.parse(text);
        html = restoreMath(html, mathBlocks, 'MATHBLOCK', true);
        html = restoreMath(html, mathInlines, 'MATHINLINE', false);
        return html.replace(
            /<pre><code class="language-(?:mermaid|mmd)">([\s\S]*?)<\/code><\/pre>/g,
            '<pre class="mermaid">$1</pre>'
        );
    }

    function removeAlertMarker(element, type) {
        var walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
        var marker = new RegExp('^\\s*\\[!' + type + '\\]\\s*', 'i');
        var node;
        while ((node = walker.nextNode())) {
            if (marker.test(node.nodeValue)) {
                node.nodeValue = node.nodeValue.replace(marker, '');
                return;
            }
        }
    }

    function decorateAlerts(target) {
        target.querySelectorAll('blockquote').forEach(function (blockquote) {
            var first = blockquote.firstElementChild;
            if (!first) return;
            var match = first.textContent.match(/^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]/i);
            if (!match) return;
            var type = match[1].toUpperCase();
            removeAlertMarker(first, type);
            var title = document.createElement('div');
            title.className = 'markdown-alert-title';
            title.textContent = ALERT_LABELS[type];
            blockquote.classList.add('markdown-alert', 'markdown-alert-' + type.toLowerCase());
            blockquote.insertBefore(title, first);
        });
    }

    function decorateTables(target) {
        target.querySelectorAll('table').forEach(function (table) {
            if (table.parentElement && table.parentElement.classList.contains('markdown-table-wrap')) return;
            var wrapper = document.createElement('div');
            wrapper.className = 'markdown-table-wrap';
            table.parentNode.insertBefore(wrapper, table);
            wrapper.appendChild(table);
        });
    }

    function decorateLinks(target) {
        target.querySelectorAll('a[href]').forEach(function (link) {
            if (/^https?:/i.test(link.getAttribute('href') || '')) {
                link.setAttribute('target', '_blank');
                link.setAttribute('rel', 'noopener noreferrer');
            }
        });
    }

    function addHeadingAnchors(target) {
        target.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(function (heading, index) {
            heading.id = 'markdown-heading-' + (index + 1);
        });
    }

    function highlightCode(target) {
        target.querySelectorAll('pre code').forEach(function (block) {
            if (block.parentElement && block.parentElement.classList.contains('mermaid')) return;
            try {
                hljs.highlightElement(block);
            } catch (error) {
                // Unknown language names fall back to readable plain code.
            }
        });
    }

    function render(source, target) {
        if (!target) throw new Error('Markdown preview target is required');
        if (!dependenciesReady()) throw new Error('Markdown rendering dependencies are unavailable');

        window.setSanitizedMarkdownHtml(target, renderSource(source));
        target.classList.add('markdown-rendered');
        decorateAlerts(target);
        decorateTables(target);
        decorateLinks(target);
        addHeadingAnchors(target);
        highlightCode(target);

        var previousTimer = mermaidTimers.get(target);
        if (previousTimer) clearTimeout(previousTimer);
        if (target.querySelector('.mermaid')) {
            var timer = setTimeout(function () {
                if (typeof window.renderMarkdownMermaid === 'function') {
                    window.renderMarkdownMermaid(target);
                }
                mermaidTimers.delete(target);
            }, 100);
            mermaidTimers.set(target, timer);
        }
        return target;
    }

    function renderWhenReady(source, target, options) {
        options = options || {};
        var attempts = options.attempts || 50;
        var delay = options.delay || 100;

        function attempt() {
            if (dependenciesReady()) {
                try {
                    render(source, target);
                    if (options.onSuccess) options.onSuccess(target);
                } catch (error) {
                    if (options.onError) options.onError(error);
                }
                return;
            }
            attempts -= 1;
            if (attempts <= 0) {
                if (options.onError) options.onError(new Error('Markdown rendering dependencies timed out'));
                return;
            }
            setTimeout(attempt, delay);
        }
        attempt();
    }

    window.DjangoDiskMarkdownRenderer = {
        decorateAlerts: decorateAlerts,
        decorateTables: decorateTables,
        render: render,
        renderSource: renderSource,
        renderWhenReady: renderWhenReady
    };
})();
