"""
ply_utils.py — Pure helper functions for PLY parsing and SPZ compression.

Extracted from export_engine.py to make these functions independently testable
and reduce the ExportEngine class size.
"""
import math
import struct
from pathlib import Path

# ── SPZ compression (pure math, no dependencies) ──────────────────────────

def compress_scale(s0: float, s1: float, s2: float) -> list:
    """Compress scale values using log encoding."""
    def encode(s):
        log_s = math.log(max(s, 1e-10))
        val = int((log_s + 10) / 20 * 255)
        return max(0, min(255, val))
    return [encode(s0), encode(s1), encode(s2)]


def compress_rotation(r0: float, r1: float, r2: float, r3: float) -> list:
    """Compress quaternion using octahedral encoding."""
    if r0 < 0:
        r0, r1, r2, r3 = -r0, -r1, -r2, -r3

    sum_abs = abs(r1) + abs(r2) + abs(r3)
    if sum_abs > 0:
        x = r1 / sum_abs
        y = r2 / sum_abs
        z = r3 / sum_abs
    else:
        x, y, z = 0, 0, 0

    if z >= 0:
        u = x
        v = y
    else:
        u = (1 - abs(y)) * (1 if x >= 0 else -1)
        v = (1 - abs(x)) * (1 if y >= 0 else -1)

    enc_u = int((u + 1) / 2 * 255)
    enc_v = int((v + 1) / 2 * 255)
    enc_z = 255 if r3 >= 0 else 0
    return [max(0, min(255, enc_u)), max(0, min(255, enc_v)), enc_z]


def compress_alpha(alpha: float) -> int:
    """Compress alpha using sigmoid inverse encoding."""
    val = int((alpha + 10) / 20 * 255)
    return max(0, min(255, val))


# ── SPZ binary writing ────────────────────────────────────────────────────

def write_spz_header(f, num_points: int):
    """Write SPZ file header."""
    f.write(b'SPZ\x00')
    f.write(struct.pack('<I', 1))       # version
    f.write(struct.pack('<I', num_points))


def write_spz_data(f, positions: list, colors: list, scales: list,
                   rotations: list, alphas: list):
    """Write SPZ data arrays."""
    import struct
    f.write(struct.pack(f'<{len(positions)}f', *positions))
    f.write(bytes(colors))
    f.write(bytes(scales))
    f.write(bytes(rotations))
    f.write(bytes(alphas))


# ── Manual PLY parsing (fallback when plyfile is not available) ───────────

def parse_ply_manual(input_file: Path) -> tuple:
    """Parse PLY file manually without plyfile dependency.
    
    Returns (positions, colors, scales, rotations, alphas) as flat lists.
    """
    positions = []
    colors = []
    scales = []
    rotations = []
    alphas = []

    with open(input_file, 'rb') as f:
        header_lines = []
        while True:
            line = f.readline().decode('ascii').strip()
            header_lines.append(line)
            if line == "end_header":
                break

        has_colors = any("property" in line and "red" in line for line in header_lines)
        has_scales = any("property" in line and "scale_0" in line for line in header_lines)
        has_rots = any("property" in line and "rot_0" in line for line in header_lines)
        has_alpha = any("property" in line and "opacity" in line for line in header_lines)

        format_line = [l for l in header_lines if l.startswith("format")]
        is_binary = len(format_line) > 0 and "binary" in format_line[0]

        if is_binary:
            vertex_props = []
            in_element = False
            num_vertices = 0
            for line in header_lines:
                if line.startswith("element vertex"):
                    in_element = True
                    num_vertices = int(line.split()[2])
                elif in_element and line.startswith("property"):
                    parts = line.split()
                    dtype = parts[1]
                    name = parts[2]
                    vertex_props.append((dtype, name))
                elif in_element and line.startswith("element"):
                    break

            import numpy as np
            dtype_map = {
                'float': '<f4', 'float32': '<f4', 'float64': '<f8',
                'uchar': '<u1', 'uint8': '<u1',
                'char': '<i1', 'int8': '<i1',
                'ushort': '<u2', 'uint16': '<u2',
                'short': '<i2', 'int16': '<i2',
                'uint': '<u4', 'uint32': '<u4',
                'int': '<i4', 'int32': '<i4'
            }

            np_dtypes = []
            for dtype, name in vertex_props:
                base_type = dtype.split('_')[0] if '_' in dtype else dtype
                np_dtype = dtype_map.get(base_type, '<f4')
                np_dtypes.append((name, np_dtype))

            if np_dtypes:
                data = np.fromfile(f, dtype=np_dtypes, count=num_vertices)
                # `row` is a numpy.void (structured scalar) which has NO .get()
                # method — use the field-name set to provide safe defaults.
                field_names = set(data.dtype.names or ())

                def _field(row, name, default):
                    return float(row[name]) if name in field_names else float(default)

                for i in range(num_vertices):
                    row = data[i]
                    x, y, z = float(row['x']), float(row['y']), float(row['z'])
                    positions.extend([x, y, z])

                    if has_colors:
                        colors.extend([int(row['red']), int(row['green']), int(row['blue']), 255])
                    else:
                        colors.extend([128, 128, 128, 255])

                    if has_scales:
                        scales.extend([
                            int((math.log(max(_field(row, 'scale_0', -2.0), 1e-10)) + 10) / 20 * 255),
                            int((math.log(max(_field(row, 'scale_1', -2.0), 1e-10)) + 10) / 20 * 255),
                            int((math.log(max(_field(row, 'scale_2', -2.0), 1e-10)) + 10) / 20 * 255),
                        ])
                    else:
                        scales.extend([0, 0, 0])

                    if has_rots:
                        rotations.extend(compress_rotation(
                            _field(row, 'rot_0', 1.0),
                            _field(row, 'rot_1', 0.0),
                            _field(row, 'rot_2', 0.0),
                            _field(row, 'rot_3', 0.0),
                        ))
                    else:
                        rotations.extend([127, 127, 127])

                    if has_alpha:
                        alphas.append(compress_alpha(_field(row, 'opacity', 1.0)))
                    else:
                        alphas.append(255)
        else:
            # ASCII PLY — the header was already consumed above, so the vertex
            # rows must be read from the remaining file body. Iterating
            # header_lines (the previous behaviour) yielded nothing past
            # end_header, so the parser silently returned zero points.
            for raw in f:
                try:
                    line = raw.decode('ascii')
                except UnicodeDecodeError:
                    continue
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        positions.extend([float(parts[0]), float(parts[1]), float(parts[2])])
                    except ValueError:
                        continue  # skip malformed/non-numeric rows
                    if has_colors and len(parts) >= 6:
                        colors.extend([int(parts[3]), int(parts[4]), int(parts[5]), 255])
                    else:
                        colors.extend([128, 128, 128, 255])

    return positions, colors, scales, rotations, alphas
