(() => {
    const cameraInput = document.getElementById('cameraInput');
    const galleryInput = document.getElementById('galleryInput');
    const cameraButton = document.getElementById('cameraButton');
    const galleryButton = document.getElementById('galleryButton');
    const startView = document.getElementById('startView');
    const resultView = document.getElementById('resultView');
    const uploadCard = document.getElementById('uploadCard');
    const uploadError = document.getElementById('uploadError');
    const loadingMessage = document.getElementById('loadingMessage');
    const resultError = document.getElementById('resultError');
    const resultImage = document.getElementById('resultImage');
    const downloadButton = document.getElementById('downloadButton');
    const printButton = document.getElementById('printButton');
    const againButton = document.getElementById('againButton');

    let generatedObjectUrl = '';
    let busy = false;

    cameraButton.addEventListener('click', () => cameraInput.click());
    galleryButton.addEventListener('click', () => galleryInput.click());

    cameraInput.addEventListener('change', event => {
        handleFile(event.target.files?.[0]);
        event.target.value = '';
    });

    galleryInput.addEventListener('change', event => {
        handleFile(event.target.files?.[0]);
        event.target.value = '';
    });

    againButton.addEventListener('click', resetApp);
    printButton.addEventListener('click', () => window.print());
    downloadButton.addEventListener('click', downloadResult);

    async function handleFile(file) {
        if (!file || busy) return;

        clearMessage(uploadError);
        clearMessage(resultError);

        if (!file.type.startsWith('image/')) {
            showMessage(uploadError, 'Please choose an image file. 📸');
            return;
        }

        busy = true;
        setBusy(true);

        const formData = new FormData();
        formData.append('photo', file);

        try {
            const response = await fetch('/api/generate/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                credentials: 'same-origin',
            });

            if (!response.ok) {
                let message = 'Something went wrong while making the coloring page. 💫';
                try {
                    const payload = await response.json();
                    if (payload.error) message = payload.error;
                } catch (_) {}
                throw new Error(message);
            }

            const blob = await response.blob();
            if (!blob.type.startsWith('image/')) {
                throw new Error('The generator returned something that was not an image.');
            }

            revokeGeneratedUrl();
            generatedObjectUrl = URL.createObjectURL(blob);
            resultImage.src = generatedObjectUrl;

            startView.hidden = true;
            resultView.hidden = false;
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } catch (error) {
            showMessage(uploadError, error.message || 'Could not make the coloring page. Please try again.');
        } finally {
            busy = false;
            setBusy(false);
        }
    }

    function setBusy(isBusy) {
        cameraButton.disabled = isBusy;
        galleryButton.disabled = isBusy;
        cameraButton.setAttribute('aria-busy', String(isBusy));
        galleryButton.setAttribute('aria-busy', String(isBusy));
        loadingMessage.hidden = !isBusy;
        uploadCard.classList.toggle('is-loading', isBusy);
    }

    function showMessage(element, message) {
        element.textContent = message;
        element.hidden = false;
    }

    function clearMessage(element) {
        element.textContent = '';
        element.hidden = true;
    }

    function resetApp() {
        revokeGeneratedUrl();
        resultImage.removeAttribute('src');
        clearMessage(uploadError);
        clearMessage(resultError);
        startView.hidden = false;
        resultView.hidden = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function revokeGeneratedUrl() {
        if (generatedObjectUrl) {
            URL.revokeObjectURL(generatedObjectUrl);
            generatedObjectUrl = '';
        }
    }

    function downloadResult() {
        if (!generatedObjectUrl) return;
        const link = document.createElement('a');
        link.href = generatedObjectUrl;
        link.download = `coloring-page-${Date.now()}.png`;
        document.body.appendChild(link);
        link.click();
        link.remove();
    }

    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (const cookie of cookies) {
            const trimmed = cookie.trim();
            if (trimmed.startsWith(name + '=')) {
                return decodeURIComponent(trimmed.slice(name.length + 1));
            }
        }
        return '';
    }
})();
