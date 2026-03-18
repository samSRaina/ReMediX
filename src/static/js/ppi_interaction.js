(function () {
    const modal = document.getElementById('ppi-preview-modal');
    const previewImage = document.getElementById('ppi-preview-image');
    const previewCaption = document.getElementById('ppi-preview-caption');
    const closeButton = document.getElementById('ppi-preview-close');
    const triggers = document.querySelectorAll('.ppi-preview-trigger');

    if (!modal || !previewImage || !previewCaption || !closeButton || triggers.length === 0) {
        return;
    }

    let lastActiveElement = null;

    function openPreview(imgEl) {
        lastActiveElement = document.activeElement;
        previewImage.src = imgEl.currentSrc || imgEl.src;
        previewImage.alt = imgEl.alt || '';
        const captionEl = imgEl.closest('figure')?.querySelector('.ppi-image-label');
        previewCaption.textContent = captionEl ? captionEl.textContent.trim() : '';

        modal.classList.add('is-open');
        modal.setAttribute('aria-hidden', 'false');
        document.body.classList.add('ppi-preview-open');
        closeButton.focus();
    }

    function closePreview() {
        modal.classList.remove('is-open');
        modal.setAttribute('aria-hidden', 'true');
        previewImage.src = '';
        previewImage.alt = '';
        previewCaption.textContent = '';
        document.body.classList.remove('ppi-preview-open');

        if (lastActiveElement && typeof lastActiveElement.focus === 'function') {
            lastActiveElement.focus();
        }
    }

    triggers.forEach((imgEl) => {
        imgEl.addEventListener('click', function () {
            openPreview(imgEl);
        });

        imgEl.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openPreview(imgEl);
            }
        });
    });

    closeButton.addEventListener('click', closePreview);

    modal.addEventListener('click', function (event) {
        if (event.target instanceof HTMLElement && event.target.dataset.closePreview === 'true') {
            closePreview();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && modal.classList.contains('is-open')) {
            closePreview();
        }
    });
})();

