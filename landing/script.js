(function () {
    'use strict';

    var THEME_KEY = '4dpocket-theme';
    var root = document.documentElement;

    // ---------- Theme ----------
    function applyTheme(theme) {
        if (theme === 'dark') {
            root.setAttribute('data-theme', 'dark');
        } else {
            root.removeAttribute('data-theme');
        }
    }

    function initTheme() {
        var stored = null;
        try { stored = localStorage.getItem(THEME_KEY); } catch (e) { /* private mode */ }
        if (stored === 'dark' || stored === 'light') {
            applyTheme(stored);
            return;
        }
        var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        applyTheme(prefersDark ? 'dark' : 'light');
    }

    function toggleTheme() {
        var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(next);
        try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* ignore */ }
    }

    initTheme();

    document.addEventListener('DOMContentLoaded', function () {
        var toggle = document.getElementById('theme-toggle');
        if (toggle) toggle.addEventListener('click', toggleTheme);

        // Follow system preference when user hasn't chosen explicitly
        if (window.matchMedia) {
            var mq = window.matchMedia('(prefers-color-scheme: dark)');
            var handler = function (e) {
                var stored = null;
                try { stored = localStorage.getItem(THEME_KEY); } catch (err) { /* ignore */ }
                if (!stored) applyTheme(e.matches ? 'dark' : 'light');
            };
            if (mq.addEventListener) mq.addEventListener('change', handler);
            else if (mq.addListener) mq.addListener(handler);
        }

        // ---------- Mobile nav ----------
        var mobileToggle = document.getElementById('nav-mobile-toggle');
        var navLinks = document.getElementById('nav-links');
        if (mobileToggle && navLinks) {
            mobileToggle.addEventListener('click', function () {
                var open = navLinks.classList.toggle('open');
                mobileToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
            });
            navLinks.querySelectorAll('a').forEach(function (link) {
                link.addEventListener('click', function () {
                    navLinks.classList.remove('open');
                    mobileToggle.setAttribute('aria-expanded', 'false');
                });
            });
        }

        // ---------- Reveal on scroll ----------
        var revealEls = document.querySelectorAll('.reveal');
        if ('IntersectionObserver' in window && revealEls.length) {
            var observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('in-view');
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
            revealEls.forEach(function (el) { observer.observe(el); });
        } else {
            revealEls.forEach(function (el) { el.classList.add('in-view'); });
        }

        // ---------- Copy buttons ----------
        var toast = document.getElementById('toast');
        var toastTimer = null;
        function showToast(message) {
            if (!toast) return;
            toast.textContent = message || 'Copied';
            toast.classList.add('visible');
            if (toastTimer) clearTimeout(toastTimer);
            toastTimer = setTimeout(function () { toast.classList.remove('visible'); }, 1800);
        }

        document.querySelectorAll('.copy-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var text = btn.getAttribute('data-copy') || '';
                var done = function () {
                    btn.classList.add('copied');
                    showToast('Copied to clipboard');
                    setTimeout(function () { btn.classList.remove('copied'); }, 1500);
                };
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text).then(done).catch(function () {
                        legacyCopy(text, done);
                    });
                } else {
                    legacyCopy(text, done);
                }
            });
        });

        function legacyCopy(text, done) {
            try {
                var ta = document.createElement('textarea');
                ta.value = text;
                ta.setAttribute('readonly', '');
                ta.style.position = 'fixed';
                ta.style.top = '-1000px';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                done && done();
            } catch (e) {
                showToast('Copy failed - please select manually');
            }
        }

        // ---------- GitHub star count ----------
        fetch('https://api.github.com/repos/onllm-dev/4DPocket')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data || typeof data.stargazers_count !== 'number') return;
                var count = data.stargazers_count;
                var formatted = count >= 1000
                    ? (count / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
                    : String(count);
                document.querySelectorAll('.nav-star-value, .star-count-value')
                    .forEach(function (el) { el.textContent = formatted; });
            })
            .catch(function () { /* keep -- fallback */ });
    });
})();
