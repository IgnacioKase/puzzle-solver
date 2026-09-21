"""Copy photos for sharing, removing metadata without recompressing JPEG pixels.

Original files are never modified. APP/COM segments and data after the main JPEG
end marker are removed, except Adobe APP14 needed for color decoding. Inputs must
have orientation 1; decoded pixels are verified against the original.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def clean_jpeg(data):
    if data[:2] != b'\xff\xd8':
        raise ValueError('Not a JPEG')
    result = bytearray(data[:2])
    pos = 2
    while pos < len(data):
        start = pos
        if data[pos] != 255:
            raise ValueError(f'Expected JPEG marker at {pos}')
        while pos < len(data) and data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker == 0xD9:
            result.extend(b'\xff\xd9')
            return bytes(result)
        if marker in [0x01, *range(0xD0, 0xD8)]:
            result.extend(data[start:pos])
            continue
        length = int.from_bytes(data[pos:pos+2], 'big')
        end = pos + length
        if length < 2 or end > len(data):
            raise ValueError('Invalid JPEG segment')
        if not (0xE0 <= marker <= 0xEF or marker == 0xFE) or marker == 0xEE:
            result.extend(data[start:end])
        pos = end
        if marker == 0xDA:
            start = pos
            while True:
                boundary = data.find(b'\xff', pos)
                if boundary < 0:
                    raise ValueError('Unterminated JPEG scan')
                next_byte = boundary + 1
                while data[next_byte] == 255:
                    next_byte += 1
                code = data[next_byte]
                if code == 0 or 0xD0 <= code <= 0xD7:
                    pos = next_byte + 1
                    continue
                result.extend(data[start:boundary])
                pos = boundary
                break
    raise ValueError('Missing JPEG end marker')


def sanitize(source, destination):
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Destination must differ from original')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as original:
        if original.getexif().get(274, 1) != 1:
            raise ValueError(f'{source}: orientation needs normalization first')
        if original.format == 'JPEG':
            destination.write_bytes(clean_jpeg(source.read_bytes()))
        elif original.format == 'PNG':
            Image.fromarray(np.array(original.convert('RGBA'))).save(destination, format='PNG')
        else:
            raise ValueError(f'Unsupported format: {original.format}')
        with Image.open(destination) as exported:
            if not np.array_equal(np.array(original.convert('RGBA')), np.array(exported.convert('RGBA'))):
                raise ValueError(f'Decoded pixels differ: {source}')
            forbidden = {'exif', 'xmp', 'icc_profile', 'mp', 'mpoffset', 'comment', 'dpi'}
            if exported.getexif() or forbidden.intersection(exported.info):
                raise ValueError(f'Metadata remains: {destination}')
    return destination.stat().st_size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    count = 0
    for source in sorted(args.source.iterdir()):
        if source.suffix.lower() in {'.jpg', '.jpeg', '.png'}:
            sanitize(source, args.destination / source.name)
            count += 1
    print(f'Exported {count} images; decoded pixels unchanged; embedded metadata removed.')
