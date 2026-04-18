(function () {
    function setDisabled(elements, disabled) {
        (elements || []).forEach((el) => {
            if (el) el.disabled = disabled;
        });
    }

    window.createRequestController = function createRequestController(config = {}) {
        const runButtons = config.runButtons || [];
        const cancelButton = config.cancelButton || null;
        let controller = null;

        function setBusy(isBusy) {
            setDisabled(runButtons, isBusy);
            if (cancelButton) cancelButton.disabled = !isBusy;
        }

        function begin() {
            if (controller) controller.abort();
            controller = new AbortController();
            setBusy(true);
            return controller;
        }

        function end(activeController) {
            // Ignore stale completions from superseded requests.
            if (activeController && controller !== activeController) {
                return;
            }
            controller = null;
            setBusy(false);
        }

        function cancel() {
            if (controller) controller.abort();
            end();
        }

        function isActive() {
            return Boolean(controller);
        }

        return { begin, end, cancel, isActive };
    };
})();
