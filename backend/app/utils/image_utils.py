from PIL import Image


def validate_magic_bytes(header_bytes: bytes) -> bool:
    """Validate that the header bytes match supported image or PDF formats (jpg, png, webp, heic, pdf)."""
    # JPEG: FF D8 FF
    if header_bytes.startswith(b'\xff\xd8\xff'):
        return True
    
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if header_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return True
        
    # PDF: %PDF-
    if header_bytes.startswith(b'%PDF-'):
        return True
        
    # WEBP: RIFF...WEBP
    if header_bytes.startswith(b'RIFF') and len(header_bytes) >= 12 and header_bytes[8:12] == b'WEBP':
        return True
        
    # HEIC: ftyp (offsets 4-8), then heic, heix, mif1, msf1
    if len(header_bytes) >= 12 and header_bytes[4:8] == b'ftyp':
        brand = header_bytes[8:12]
        if brand in (b'heic', b'heix', b'mif1', b'msf1', b'hevc', b'hevx'):
            return True
            
    return False

def strip_exif_keep_orientation(image_path: str):
    """Strip all EXIF tags except orientation to protect privacy while maintaining proper image rotation."""
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                return
            
            # The EXIF tag for Orientation is 274 (0x0112)
            orientation_tag = 274
            orientation = exif.get(orientation_tag)
            
            exif.clear()
            
            if orientation is not None:
                exif[orientation_tag] = orientation
                
            img.save(image_path, exif=exif)
    except Exception as e:
        print(f"Failed to strip EXIF from {image_path}: {e}")
