def hook_window_open(page):
    """
    Injeta hook para capturar URLs abertas via window.open().
    Retorna lista mutável onde os URLs serão armazenados.
    """

    captured = []

    page.expose_function("_captureWindowOpen", lambda url: captured.append(url))

    page.add_init_script("""
        (() => {
            const originalOpen = window.open;
            window.open = function(url, ...args) {
                try {
                    if (url) {
                        window._captureWindowOpen(url);
                    }
                } catch (e) {}
                return originalOpen.apply(this, arguments);
            };
        })();
    """)

    return captured
