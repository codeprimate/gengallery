class GalleryLogin {
    constructor(galleryId, privateGalleryIdHash) {
        this.galleryId = galleryId;
        this.privateGalleryIdHash = privateGalleryIdHash;
        this.loadingState = document.getElementById('loadingState');
        this.loginForm = document.getElementById('loginForm');
        this.passwordInput = document.getElementById('password');
        this.submitButton = document.getElementById('submitButton');
        this.errorMessage = document.getElementById('errorMessage');

        this.init();
    }

    async init() {
        const hasValidCredentials = await this.checkSavedCredentials();
        if (!hasValidCredentials) {
            this.loadingState.classList.add('hidden');
            this.loginForm.classList.remove('hidden');
            this.passwordInput.focus();
        }

        this.passwordInput.addEventListener('input', () => {
            this.submitButton.disabled = this.passwordInput.value.length === 0;
        });

        this.loginForm.addEventListener('submit', this.handleSubmit.bind(this));
    }

    async hashString(input) {
        const encoder = new TextEncoder();
        const data = encoder.encode(input);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    async generatePrivateGalleryId(password) {
        const hashHex = await this.hashString(`${this.galleryId}:${password}`);
        return hashHex.slice(0, 16); // Truncate to 16 characters
    }

    getHashFromUrl() {
        return window.location.hash;
    }

    redirectToGallery(privateGalleryId) {
        const hash = this.getHashFromUrl();
        window.location.href = `./${privateGalleryId}.html${hash}`;
    }

    savePrivateGalleryId(privateGalleryId) {
        localStorage.setItem(`gallery_${this.galleryId}_private_id`, privateGalleryId);
    }

    getSavedPrivateGalleryId() {
        return localStorage.getItem(`gallery_${this.galleryId}_private_id`);
    }

    async checkSavedCredentials() {
        const savedPrivateGalleryId = this.getSavedPrivateGalleryId();
        if (savedPrivateGalleryId) {
            const savedPrivateGalleryIdHash = await this.hashString(savedPrivateGalleryId);
            if (savedPrivateGalleryIdHash === this.privateGalleryIdHash) {
                this.redirectToGallery(savedPrivateGalleryId);
                return true;
            }
        }
        return false;
    }

    async handleSubmit(e) {
        e.preventDefault();
        const password = this.passwordInput.value;

        try {
            const assertedPrivateGalleryId = await this.generatePrivateGalleryId(password);
            const assertedPrivateGalleryIdHash = await this.hashString(assertedPrivateGalleryId);

            if (assertedPrivateGalleryIdHash === this.privateGalleryIdHash) {
                this.savePrivateGalleryId(assertedPrivateGalleryId);
                this.redirectToGallery(assertedPrivateGalleryId);
            } else {
                this.errorMessage.textContent = 'Incorrect password. Please try again.';
                this.errorMessage.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Hashing error:', error);
            this.errorMessage.textContent = 'An error occurred. Please try again.';
            this.errorMessage.classList.remove('hidden');
        }
    }
}

class GalleryLock {
    constructor(galleryId, privateGalleryId) {
        this.galleryId = galleryId;
        this.privateGalleryId = privateGalleryId;
        this.lockIcon = document.getElementById('lockIcon');
        this.openLock = this.lockIcon.querySelector('.open-lock');
        this.closedLock = this.lockIcon.querySelector('.closed-lock');

        this.init();
    }

    init() {
        this.lockIcon.addEventListener('mouseover', this.showClosedLock.bind(this));
        this.lockIcon.addEventListener('mouseout', this.showOpenLock.bind(this));
        this.lockIcon.addEventListener('click', this.handleLockClick.bind(this));
    }

    showClosedLock() {
        this.openLock.classList.add('hidden');
        this.closedLock.classList.remove('hidden');
    }

    showOpenLock() {
        this.openLock.classList.remove('hidden');
        this.closedLock.classList.add('hidden');
    }

    handleLockClick(event) {
        event.preventDefault(); // Prevent any default button behavior
        localStorage.removeItem(`gallery_${this.galleryId}_private_id`);
        window.location.href = `./index.html`;
    }
}