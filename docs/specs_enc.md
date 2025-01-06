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
- **Private Gallery ID Hash**: SHA-256(private_gallery_id) - stored for verification
- **Encryption Key**: SHA-256(private_gallery_id)
- **IV**: SHA-256(`imageId`)[:16] - unique per image
- **Image ID**: For encrypted galleries: SHA-256(`galleryId:filename`)[:16]
  For unencrypted galleries: MD5(`galleryId:filename`)[:12]

### Gallery Metadata Structure
The gallery metadata (stored in metadata/GALLERY_ID/index.json) includes:
```json
{
  "id": "gallery_id",
  "encrypted": true,
  "private_gallery_id": "sha256_hash[:16]",  // First 16 chars of SHA-256(galleryId:password)
  "private_gallery_id_hash": "sha256_hash",  // SHA-256(private_gallery_id) for verification
  "unlisted": true,  // Encrypted galleries are always unlisted
  // ... other standard gallery fields ...
}
```

### Security Model Updates
- Private gallery ID is never stored in metadata
- Only the hash of the private gallery ID is stored for verification
- Encrypted galleries are automatically marked as unlisted
- Image IDs for encrypted galleries use SHA-256 instead of MD5
- All encryption/decryption parameters are deterministically generated
- No encryption keys or IVs are stored in metadata

### Security Guarantees
- No unencrypted content in output directory (except metadata)
- Password never stored (only private gallery ID hash for verification)
- Deterministic encryption allows for content verification
- All encryption/decryption happens client-side
- Each image has a unique IV derived from its ID
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
   - Generate image ID using SHA-256(`galleryId:filename`)[:16]
   - Generate encryption key from private gallery ID
   - Generate unique IV for each image from image ID
   - Process and encrypt images
   - Store minimal metadata without encryption parameters

### Gallery Processing (gallery_processor.py)
1. For encrypted galleries:
   - Generate private gallery ID: SHA-256(`galleryId:password`)[:16]
   - Generate verification hash: SHA-256(private_gallery_id)
   - Store gallery metadata:
     - Set encrypted: true
     - Set unlisted: true automatically
     - Store private gallery ID hash for verification
     - Clear private gallery ID field
     - Include standard gallery information

### HTML Generation (generator.py)
1. Generate special template for encrypted galleries
2. Include decryption code and Web Crypto API handling
3. Include SVG placeholders in template
4. Don't embed sensitive metadata in HTML

## Template Structure

### Encrypted Gallery Template (encrypted_gallery.html.jinja)
The encrypted gallery template includes:
- Gallery header with encrypted cover image
- Loading overlays with animated spinners
- Image grid with encrypted thumbnails
- SVG placeholders for initial image display
- Navigation elements for gallery browsing

### Encrypted Single Image Template (encrypted_image.html.jinja)
The single image view template includes:
- Full-size encrypted image display
- Previous/Next navigation arrows
- Loading overlays with animated spinners
- SVG placeholders for initial state
- Full-screen image view support

### Template Features
- Uses SVG placeholders for initial image display
- Includes loading overlays with animated spinners
- Supports lazy loading through IntersectionObserver
- Handles navigation between images
- Manages memory through image type limits
- Uses Tailwind CSS for styling
- Includes data attributes for encryption type and content type
- Provides responsive image grid layout
- Implements full-screen image view with navigation

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
- Enforces strict limits per image type:
  - Full size: 1 image
  - Cover: 3 images
  - Thumbnails: 10 images
- Automatically revokes object URLs for off-screen images

### Authentication Flow
1. User visits gallery URL
2. Enters password
3. Client-side generates:
   - Private gallery ID = SHA-256(`galleryId:password`)[:16]
   - Verification hash = SHA-256(private_gallery_id)
4. If verification hash matches stored hash:
   - Save private gallery ID to localStorage
   - Redirect to gallery page
5. Gallery page uses stored private gallery ID to:
   - Generate encryption key: SHA-256(private_gallery_id)
   - Generate IVs for each image: SHA-256(`imageId`)[:16]
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
