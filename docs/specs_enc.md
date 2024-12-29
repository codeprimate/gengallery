# Photo Gallery Encryption Specification

This document outlines the encryption features for the static photo gallery generator, enabling private galleries that can only be viewed with the correct password.

## Gallery Configuration

Encryption is enabled by adding a single flag in the gallery's YAML file:

```yaml
title: "Private Family Photos"
encrypted: true  # Only flag needed to enable encryption
# ... other standard gallery fields ...
```

## Security Model

### Key Generation and Authentication
- **Private Gallery ID**: Generated as SHA-256(`galleryId:password`)[:16]
- **Authentication**: Verified through private gallery ID hash match
- **Encryption Key**: Private Gallery ID serves as encryption salt
- **File Names**: Generated as SHA-256(`privateGalleryId:originalBasename`)[:16]

### Security Guarantees
- No unencrypted content in output directory
- No password storage (only private gallery ID hash for verification)
- All encryption/decryption happens client-side
- No server-side components required
- Encrypted files are indistinguishable from random data
- File names provide no information about original content

## File Structure

Encrypted galleries maintain the same structure as regular galleries:
```
export/galleries/YYYYMMDD/
├── index.html  # Login page for encrypted galleries
├── {privateGalleryId}.html  # Actual gallery page (accessed after authentication)
├── cover/
│   └── {encryptedBasename}.jpg  # Filename from image metadata
├── full/
│   └── {encryptedBasename}.jpg  # Filename from image metadata
├── metadata/
│   └── {encryptedBasename}.json  # Contains encrypted filename mapping
└── thumbnail/
    └── {encryptedBasename}.jpg  # Filename from image metadata
```

## Processing Pipeline

### Image Processing (image_processor.py)
1. Check if gallery is encrypted from gallery.yml
2. For encrypted galleries:
   - Generate encrypted basenames using private gallery ID and original filename
   - Process images normally (resize, extract EXIF)
   - Remove any unencrypted images from output directories
   - Store only encrypted versions with hashed filenames

### Gallery Processing (gallery_processor.py)
1. For encrypted galleries:
   - Generate private gallery ID from gallery ID and password
   - Generate private gallery ID hash for verification
   - Use private gallery ID for file naming and encryption
   - Create login page (index.html)
   - Create actual gallery page ({privateGalleryId}.html)
2. Store minimal gallery metadata:
   - Title
   - Date
   - Private gallery ID hash (for verification)
   - No sensitive metadata

### HTML Generation (generator.py)
1. Generate special template for encrypted galleries
2. Include decryption code and Web Crypto API handling
3. Include SVG placeholders in template
4. Don't embed sensitive metadata in HTML

## Template Structure

### Encrypted Gallery Template (encrypted_gallery.html.jinja)
The encrypted gallery template includes:

```html
<head>
    <!-- Standard meta tags -->
    <meta name="encrypted-gallery" content="true">
</head>
<body>
    <!-- Gallery Header with Cover Image -->
    <img class="encrypted-image" 
         src="#encrypted-placeholder"
         data-encrypted-url="{{ gallery.cover.path }}"
         data-encrypted-type="cover"
         alt="Encrypted Image">

    <!-- Image Grid -->
    <div class="grid">
        {% for image in gallery.images %}
        <div class="relative">
            <img class="encrypted-image" 
                 src="#encrypted-placeholder"
                 data-encrypted-url="{{ image.thumbnail_path }}"
                 data-encrypted-type="thumbnail"
                 alt="Encrypted Image">
            
            <!-- Loading Overlay -->
            <div class="encrypted-overlay">
                <!-- Loading spinner SVG -->
            </div>
        </div>
        {% endfor %}
    </div>
</body>
```

### Encrypted Single Image Template (encrypted_image.html.jinja)
The single image view template includes:

```html
<body>
    <!-- Main Image Container -->
    <div class="relative">
        <img class="encrypted-image" 
             src="#encrypted-placeholder"
             data-encrypted-url="{{ image.path }}"
             data-encrypted-type="full"
             alt="Encrypted Image">
        
        <!-- Navigation Thumbnails -->
        {% if prev_image %}
        <img class="nav-thumbnail encrypted-image" 
             src="#encrypted-placeholder"
             data-encrypted-url="{{ prev_image.thumbnail_path }}"
             data-encrypted-type="thumbnail"
             alt="Previous">
        {% endif %}
        
        {% if next_image %}
        <img class="nav-thumbnail encrypted-image" 
             src="#encrypted-placeholder"
             data-encrypted-url="{{ next_image.thumbnail_path }}"
             data-encrypted-type="thumbnail"
             alt="Next">
        {% endif %}
    </div>
</body>
```

### Template Features
- Uses SVG placeholders for initial image display
- Includes loading overlays with spinners
- Supports lazy loading through IntersectionObserver
- Handles navigation between images
- Manages memory through image type limits

## Client-Side Implementation

### EncryptedGallery Class
Manages decryption and display of encrypted images:

```javascript
new EncryptedGallery(galleryId, privateGalleryId, {
    limits: {
        full: 1,      // One full-size image
        cover: 3,     // Three cover images
        thumbnail: 10  // Ten thumbnails
    },
    mode: 'gallery',  // or 'single' for single image view
    imageSelector: '.encrypted-image',
    overlaySelector: '.encrypted-overlay'
});
```

### Image Loading States
1. Initial State: SVG placeholder with lock icon
2. Loading: Overlay with animated spinner
3. Decrypting: Progress indicator
4. Success: Fade in decrypted image
5. Error: Show error message in overlay

### Memory Management
- Tracks decrypted images by type (full, cover, thumbnail)
- Enforces strict limits per image type
- Automatically revokes object URLs for off-screen images
- Cleans up all resources on page unload

### Authentication Flow
1. User visits gallery URL (index.html)
2. Enters password
3. Client-side generates private gallery ID
4. If private gallery ID hash matches:
   - Save private gallery ID to localStorage
   - Redirect to {privateGalleryId}.html
5. Gallery page uses stored private gallery ID to:
   - Generate correct encrypted file paths
   - Decrypt content as needed

### Image Display
1. Template includes SVG placeholders in hidden element:
   ```html
   <div hidden>
     <!-- Thumbnail placeholder with lock icon -->
     <svg id="encrypted-thumb-placeholder" viewBox="0 0 300 200">
       <rect width="100%" height="100%" fill="#eee"/>
       <path class="lock-icon" d="..." fill="#999"/>
     </svg>
     
     <!-- Full-size placeholder with loading indicator -->
     <svg id="encrypted-full-placeholder" viewBox="0 0 1024 768">
       <rect width="100%" height="100%" fill="#f5f5f5"/>
       <path class="lock-icon" d="..." fill="#666"/>
       <circle class="loading-indicator" cx="512" cy="384" r="32"/>
     </svg>
   </div>
   ```

2. Gallery template uses placeholders for encrypted images:
   ```html
   <img src="#encrypted-thumb-placeholder" 
        data-encrypted-url="/galleries/YYYYMMDD/thumbnail/{encryptedBasename}.jpg"
        data-encrypted-iv="{iv}"
        class="encrypted-image"
        alt="Encrypted image" />
   ```

3. Client-side JavaScript:
   - Finds all images with class "encrypted-image"
   - For each visible image:
     - Shows appropriate SVG placeholder during loading
     - Fetches encrypted data from data-encrypted-url
     - Decrypts using Web Crypto API
     - Creates blob URL for decrypted data
     - Replaces src with blob URL
   - Cleans up blob URLs when images scroll out of view

### Performance Optimizations
- Use IntersectionObserver for lazy loading
- Only decrypt images as they become visible
- Clean up blob URLs and memory for off-screen images
- Maintain strict decryption limits:
  - Full-size images: 1 concurrent
  - Cover images: 3 concurrent
  - Thumbnails: 10 concurrent
- Implement LRU (Least Recently Used) cache for each image type
- Force cleanup of older items when limits are reached
- Cache recently decrypted images in memory (within defined limits)
- SVG placeholders eliminate need for placeholder image requests

### Memory Management
- Implement separate LRU queues for each image type:
  ```javascript
  const memoryLimits = {
    full: 1,    // Only one full-size image at a time
    cover: 3,   // Up to three cover images
    thumb: 10   // Up to ten thumbnails
  };
  ```
- Automatically evict oldest items when limits are reached
- Prioritize decryption based on image type and viewport visibility
- Clear all decrypted images when navigating away or closing gallery

### SVG Placeholder States
- Initial: Lock icon only
- Loading: Animated spinner + lock icon
- Error: Warning icon + lock icon
- Success: Fade out as decrypted image loads

## Security Considerations

### Browser Security
- No storage of decrypted data to disk
- Clear memory when navigating away
- Private gallery ID stored only in localStorage
- Optional session-only caching

### Known Limitations
- Directory structure remains visible
- File sizes remain visible
- Number of images remains visible
- Browser memory constraints limit concurrent decryption

## Implementation Notes

### Required Libraries
- Web Crypto API (browser)
- SHA-256 for key generation
- AES-GCM for content encryption

### Browser Compatibility
- Modern browsers with Web Crypto API support
- Fallback messaging for unsupported browsers
- Minimum browser versions:
  - Chrome 60+
  - Firefox 55+
  - Safari 11+
  - Edge 79+

### Development Considerations
- Test encrypted and unencrypted galleries
- Verify cleanup of unencrypted files
- Ensure proper error handling
- Implement graceful fallbacks
- Monitor memory usage during decryption
