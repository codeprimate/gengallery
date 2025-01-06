/**
 * Handles gallery login functionality and password verification.
 */
class GalleryLogin {
    /**
     * @param {string} galleryId - Unique identifier for the gallery
     * @param {string} privateGalleryIdHash - Hash of the private gallery ID for verification
     */
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

    /**
     * Initializes the login form and checks for saved credentials.
     * @returns {Promise<void>}
     */
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

    /**
     * Generates a SHA-256 hash of the input string.
     * @param {string} input - String to hash
     * @returns {Promise<string>} Hexadecimal hash string
     */
    async hashString(input) {
        const encoder = new TextEncoder();
        const data = encoder.encode(input);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
    }

    /**
     * Generates a private gallery ID by hashing the gallery ID and password.
     * @param {string} password - User provided password
     * @returns {Promise<string>} Truncated hash string (16 characters)
     */
    async generatePrivateGalleryId(password) {
        const hashHex = await this.hashString(`${this.galleryId}:${password}`);
        return hashHex.slice(0, 16); // Truncate to 16 characters
    }

    /**
     * Retrieves the current URL hash fragment.
     * @returns {string} URL hash fragment
     */
    getHashFromUrl() {
        return window.location.hash;
    }

    /**
     * Redirects to the gallery page with the provided ID and current hash.
     * @param {string} privateGalleryId - Private gallery identifier
     */
    redirectToGallery(privateGalleryId) {
        const hash = this.getHashFromUrl();
        window.location.href = `./${privateGalleryId}.html${hash}`;
    }

    /**
     * Saves the private gallery ID to local storage.
     * @param {string} privateGalleryId - Private gallery identifier to save
     */
    savePrivateGalleryId(privateGalleryId) {
        localStorage.setItem(`gallery_${this.galleryId}_private_id`, privateGalleryId);
    }

    /**
     * Retrieves the saved private gallery ID from local storage.
     * @returns {string|null} Saved private gallery ID or null if not found
     */
    getSavedPrivateGalleryId() {
        return localStorage.getItem(`gallery_${this.galleryId}_private_id`);
    }

    /**
     * Checks for saved credentials and validates them.
     * @returns {Promise<boolean>} True if valid credentials exist
     */
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

    /**
     * Handles form submission and password verification.
     * @param {Event} e - Form submission event
     * @returns {Promise<void>}
     */
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
                this.passwordInput.value = '';
                this.errorMessage.classList.remove('hidden');
            }
        } catch (error) {
            console.error('Hashing error:', error);
            this.errorMessage.textContent = 'An error occurred. Please try again.';
            this.errorMessage.classList.remove('hidden');
        }
    }
}

/**
 * Manages the gallery lock/unlock UI and functionality.
 */
class GalleryLock {
    /**
     * @param {string} galleryId - Unique identifier for the gallery
     * @param {string} privateGalleryId - Private ID for the gallery
     */
    constructor(galleryId, privateGalleryId) {
        this.galleryId = galleryId;
        this.privateGalleryId = privateGalleryId;
        this.lockIcon = document.getElementById('lockIcon');
        this.openLock = this.lockIcon.querySelector('.open-lock');
        this.closedLock = this.lockIcon.querySelector('.closed-lock');

        // Find any active EncryptedGallery instance
        this.encryptedGallery = window._encryptedGallery;

        this.init();
    }

    /**
     * Initializes event listeners for the lock icon.
     */
    init() {
        this.lockIcon.addEventListener('mouseover', this.showClosedLock.bind(this));
        this.lockIcon.addEventListener('mouseout', this.showOpenLock.bind(this));
        this.lockIcon.addEventListener('click', this.handleLockClick.bind(this));
    }

    /**
     * Shows the closed lock icon state.
     */
    showClosedLock() {
        this.openLock.classList.add('hidden');
        this.closedLock.classList.remove('hidden');
    }

    /**
     * Shows the open lock icon state.
     */
    showOpenLock() {
        this.openLock.classList.remove('hidden');
        this.closedLock.classList.add('hidden');
    }

    /**
     * Handles lock icon click event, clearing credentials and redirecting.
     * @param {Event} event - Click event
     */
    handleLockClick(event) {
        event.preventDefault();

        // Clean up encrypted gallery if it exists
        if (this.encryptedGallery) {
            this.encryptedGallery.cleanup();
            window._encryptedGallery = null;
        }

        // Clear all sensitive data from localStorage
        localStorage.removeItem(`gallery_${this.galleryId}_private_id`);

        // Clear any sensitive data from memory
        this.privateGalleryId = null;
        
        // Force garbage collection hints on sensitive data
        if (window.gc) {
            window.gc();
        }

        // Redirect to login page
        window.location.href = `./index.html`;
    }
}

/**
 * Handles encrypted image loading and decryption in galleries.
 */
class EncryptedGallery {
    /**
     * @param {string} galleryId - Unique identifier for the gallery
     * @param {string} privateGalleryId - Private gallery ID to use as encryption key
     * @param {Object} [options] - Configuration options
     */
    constructor(galleryId, privateGalleryId, options = {}) {
        this.galleryId = galleryId;
        this.privateGalleryId = privateGalleryId;
        this.options = {
            placeholderSelector: options.placeholderSelector || '#encrypted-placeholder',
            imageSelector: options.imageSelector || '.encrypted-image',
            overlaySelector: options.overlaySelector || '.encrypted-overlay',
            mode: options.mode || 'gallery',
            maxBufferSize: options.maxBufferSize || 10 // Keep last 10 images in memory
        };

        // Simplified tracking - just keep decrypted URLs and failed images
        this.visibleImages = new Set(); // Add tracking of visible images
        this.decryptedImages = new Map(); // url -> objectUrl
        this.failedImages = new Set();
        this.errorLogCount = 0;
        this.maxErrorLogs = 5;

        if (this.options.mode === 'single') {
            this.decryptSingleImage();
        } else {
            this.initIntersectionObserver();
        }
        
        window.addEventListener('unload', () => this.cleanup());

        // Add click handler for full image links
        document.addEventListener('click', async (e) => {
            const link = e.target.closest('.full-image-link');
            if (link) {
                e.preventDefault();
                await this.handleFullImageClick(link);
            }
        });

        // Store instance globally for access by GalleryLock
        window._encryptedGallery = this;
    }

    /**
     * Decrypts a single image for single image view mode.
     * @returns {Promise<void>}
     */
    async decryptSingleImage() {
        const mainImage = document.querySelector(this.options.imageSelector);
        if (!mainImage) return;

        try {
            const overlay = mainImage.parentElement.querySelector(this.options.overlaySelector);
            if (overlay) overlay.style.display = 'flex';

            const url = mainImage.dataset.encryptedUrl;
            const decryptedBlob = await this.fetchAndDecrypt(url);
            
            const objectUrl = URL.createObjectURL(decryptedBlob);
            mainImage.src = objectUrl;
            
            // Store in our Map instead of the old .full collection
            this.decryptedImages.set(url, objectUrl);
            
            if (overlay) overlay.style.display = 'none';

            await this.decryptNavigationThumbnails();

        } catch (error) {
            console.error('Decryption failed:', error);
            const overlay = mainImage.parentElement.querySelector(this.options.overlaySelector);
            if (overlay) {
                overlay.innerHTML = '<div class="text-red-600">Decryption failed</div>';
            }
        }
    }

    /**
     * Decrypts thumbnail images for navigation.
     * @returns {Promise<void>}
     */
    async decryptNavigationThumbnails() {
        const navThumbnails = document.querySelectorAll('.nav-thumbnail');
        for (const thumb of navThumbnails) {
            if (thumb.dataset.encryptedUrl) {
                try {
                    const url = thumb.dataset.encryptedUrl;
                    const decryptedBlob = await this.fetchAndDecrypt(url);
                    const objectUrl = URL.createObjectURL(decryptedBlob);
                    thumb.src = objectUrl;
                    // Store in our Map instead of the old .thumbnail collection
                    this.decryptedImages.set(url, objectUrl);
                } catch (error) {
                    console.error('Navigation thumbnail decryption failed:', error);
                }
            }
        }
    }

    /**
     * Initializes intersection observer for lazy loading images.
     * @returns {Promise<void>}
     */
    async initIntersectionObserver() {
        const options = {
            root: null,
            rootMargin: '50px',
            threshold: 0.1
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    this.handleImageVisible(entry.target);
                } else {
                    this.handleImageHidden(entry.target);
                }
            });
        }, options);

        // Observe all encrypted images
        document.querySelectorAll(this.options.imageSelector).forEach(img => {
            observer.observe(img);
        });
    }

    /**
     * Validates that a blob contains valid image data
     * @param {Blob} blob - The blob to validate
     * @returns {Promise<boolean>}
     */
    async isValidImage(blob) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => {
                const arr = new Uint8Array(reader.result).subarray(0, 16);
                const header = Array.from(arr).map(x => x.toString(16).padStart(2, '0')).join('');
                // Check for JPEG header (FF D8 FF)
                const isValid = header.startsWith('ffd8ff');
                resolve(isValid);
            };
            reader.onerror = () => resolve(false);
            reader.readAsArrayBuffer(blob);
        });
    }

    /**
     * Handles image elements becoming visible in the viewport.
     */
    async handleImageVisible(img) {
        const url = img.dataset.encryptedUrl;
        if (!url || this.failedImages.has(url)) return;

        // Track this image as visible
        this.visibleImages.add(url);
        
        const overlay = img.parentElement.querySelector(this.options.overlaySelector);
        if (overlay) overlay.style.display = 'flex';

        try {
            // Check if already decrypted
            if (this.decryptedImages.has(url)) {
                img.src = this.decryptedImages.get(url);
                if (overlay) overlay.style.display = 'none';
                return;
            }

            // Decrypt image
            const decryptedBlob = await this.fetchAndDecrypt(url);
            
            if (!await this.isValidImage(decryptedBlob)) {
                throw new Error('Invalid image data');
            }

            const objectUrl = URL.createObjectURL(decryptedBlob);
            this.decryptedImages.set(url, objectUrl);
            
            img.src = objectUrl;
            img.srcset = '';
            
            if (overlay) overlay.style.display = 'none';

        } catch (error) {
            this.logError('Decryption failed for', url, error);
            this.failedImages.add(url);
            
            if (overlay) {
                overlay.style.display = 'flex';
                overlay.innerHTML = '<div class="text-red-600">Decryption failed</div>';
            }
            
            if (img.src !== this.options.placeholderSelector) {
                img.src = this.options.placeholderSelector;
            }
        }
    }

    /**
     * Handles image elements leaving the viewport.
     * @param {HTMLImageElement} img - Image element that left viewport
     */
    handleImageHidden(img) {
        const url = img.dataset.encryptedUrl;
        if (!url) return;

        // Remove from visible set
        this.visibleImages.delete(url);
        
        // Clean up excess images after a short delay
        // (in case user is just quickly scrolling)
        setTimeout(() => this.cleanupExcessImages(), 1000);
    }

    cleanupExcessImages() {
        // Don't cleanup if we're under the buffer size
        if (this.decryptedImages.size <= this.options.maxBufferSize) return;

        // Get all decrypted URLs that aren't currently visible
        const invisibleUrls = Array.from(this.decryptedImages.keys())
            .filter(url => !this.visibleImages.has(url));

        // Sort by when they were last visible (if we tracked that)
        // For now, just remove the first ones up to the buffer size
        const urlsToRemove = invisibleUrls.slice(
            0, 
            this.decryptedImages.size - this.options.maxBufferSize
        );

        for (const url of urlsToRemove) {
            const objectUrl = this.decryptedImages.get(url);
            URL.revokeObjectURL(objectUrl);
            this.decryptedImages.delete(url);
        }
    }

    /**
     * Fetches and decrypts an encrypted image.
     */
    async fetchAndDecrypt(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const encryptedData = await response.arrayBuffer();
        const imageId = url.split('/').pop().split('.')[0];
        
        const { key, iv } = await deriveEncryptionParams(
            this.galleryId, 
            imageId, 
            this.privateGalleryId
        );
        
        const decrypted = await crypto.subtle.decrypt(
            { name: 'AES-CBC', iv },
            key,
            encryptedData
        );
        
        return new Blob([decrypted], { type: 'image/jpeg' });
    }

    /**
     * Performs cleanup by revoking object URLs and clearing sensitive data.
     */
    cleanup() {
        // Revoke all object URLs
        for (const objectUrl of this.decryptedImages.values()) {
            URL.revokeObjectURL(objectUrl);
        }
        
        // Clear all collections
        this.decryptedImages.clear();
        this.visibleImages.clear();
        this.failedImages.clear();

        // Clear sensitive data
        this.privateGalleryId = null;
        
        // Remove references to DOM elements
        this.options = null;
    }

    /**
     * Handles error logging.
     * @param {...any} args - Error arguments
     */
    logError(...args) {
        if (this.errorLogCount < this.maxErrorLogs) {
            console.error(...args);
            this.errorLogCount++;
            
            if (this.errorLogCount === this.maxErrorLogs) {
                console.warn('Further errors will be suppressed');
            }
        }
    }

    /**
     * Handles full image click event.
     * @param {Event} e - Click event
     */
    async handleFullImageClick(link) {
        const img = link.querySelector(this.options.imageSelector);
        if (!img) return;

        const fullUrl = img.dataset.fullUrl;
        if (!fullUrl) return;

        try {
            // Show loading state
            const overlay = img.parentElement.querySelector(this.options.overlaySelector);
            if (overlay) overlay.style.display = 'flex';

            // Check if already decrypted
            if (this.decryptedImages.has(fullUrl)) {
                window.open(this.decryptedImages.get(fullUrl));
                return;
            }

            // Decrypt full image
            const decryptedBlob = await this.fetchAndDecrypt(fullUrl);
            
            if (!await this.isValidImage(decryptedBlob)) {
                throw new Error('Invalid image data');
            }

            const objectUrl = URL.createObjectURL(decryptedBlob);
            this.decryptedImages.set(fullUrl, objectUrl);
            
            // Open in new tab
            window.open(objectUrl);

        } catch (error) {
            this.logError('Full image decryption failed:', error);
            alert('Failed to load full image');
        } finally {
            const overlay = img.parentElement.querySelector(this.options.overlaySelector);
            if (overlay) overlay.style.display = 'none';
        }
    }
}

/**
 * Derives encryption parameters for decrypting gallery images.
 * @param {string} galleryId - Gallery ID
 * @param {string} imageId - Image ID 
 * @param {string} privateGalleryId - Private gallery ID to use as encryption key
 * @returns {Promise<{key: CryptoKey, iv: Uint8Array}>}
 */
async function deriveEncryptionParams(galleryId, imageId, privateGalleryId) {
    const encoder = new TextEncoder();
    
    // Hash the private gallery ID to get a consistent key length
    const keyBuffer = await crypto.subtle.digest(
        'SHA-256',
        encoder.encode(privateGalleryId)
    );
    
    // Get IV from image ID hash (matching Python)
    const ivBuffer = await crypto.subtle.digest(
        'SHA-256',
        encoder.encode(imageId)
    );
    const iv = new Uint8Array(ivBuffer.slice(0, 16));
    
    // Import the derived bits as an AES-CBC key
    const key = await crypto.subtle.importKey(
        'raw',
        keyBuffer,
        { name: 'AES-CBC' },
        false,
        ['decrypt']
    );
    
    return { key, iv };
}