import os
import shutil
import subprocess
import struct
import math
from pathlib import Path
from typing import Optional, Callable

from .base_engine import BaseEngine


class ExportEngine(BaseEngine):
    """Engine for exporting PLY files to various formats."""

    SUPPORTED_FORMATS = ["spz", "glb", "obj", "ply", "xyz"]

    def __init__(self, logger_callback: Optional[Callable] = None) -> None:
        super().__init__("Export", logger_callback)

    def is_available(self) -> bool:
        """Check if export tools are available."""
        return True

    def export(
        self,
        input_path: str,
        output_path: str,
        output_format: str,
        scale: float = 1.0,
        options: dict = None,
    ) -> bool:
        """Export PLY to target format.

        Parameters
        ----------
        input_path: str
            Path to input PLY file.
        output_path: str
            Destination path (directory or file).
        output_format: str
            Target format (glb, obj, ply, xyz).
        scale: float
            Scale factor for export.

        Returns
        -------
        bool
            True on success.
        """
        input_file = Path(input_path)
        output_dir = Path(output_path)

        if not input_file.exists():
            self.log(f"Erreur: fichier introuvable {input_file}")
            return False

        output_dir.mkdir(parents=True, exist_ok=True)

        opts = options or {}
        if output_format == "ply":
            return self._export_ply(input_file, output_dir, opts)
        elif output_format == "xyz":
            return self._export_xyz(input_file, output_dir, opts)
        elif output_format == "obj":
            return self._export_obj(input_file, output_dir, opts)
        elif output_format == "glb":
            return self._export_glb(input_file, output_dir, opts)
        elif output_format == "spz":
            return self._export_spz(input_file, output_dir, opts)
        else:
            self.log(f"Format non supporté: {output_format}")
            return False

    def _export_ply(self, input_file: Path, output_dir: Path, opts: dict) -> bool:
        """Re-export PLY with optional optimizations."""
        output_file = output_dir / input_file.name
        try:
            # Option: convert to ASCII format
            if opts.get('ascii_format', False):
                return self._export_ply_ascii(input_file, output_file)
            # Option: compress with gzip
            elif opts.get('compress', False):
                import gzip
                output_file = output_dir / (input_file.name + '.gz')
                with open(input_file, 'rb') as f_in:
                    with gzip.open(output_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                self.log(f"Compressé: {output_file}")
                return True
            else:
                shutil.copy2(input_file, output_file)
                self.log(f"Copié: {output_file}")
                return True
        except Exception as e:
            self.log(f"Erreur: {e}")
            return False

    def _export_ply_ascii(self, input_file: Path, output_file: Path) -> bool:
        """Convert binary PLY to ASCII format."""
        try:
            try:
                from plyfile import PlyData
                ply = PlyData.read(str(input_file))
                ply.write(str(output_file), text=True)
                self.log(f"Exporté PLY ASCII: {output_file}")
                return True
            except ImportError:
                self.log("plyfile requis pour conversion ASCII. pip install plyfile")
                return False
        except Exception as e:
            self.log(f"Erreur conversion PLY ASCII: {e}")
            return False

    def _export_xyz(self, input_file: Path, output_dir: Path, opts: dict) -> bool:
        """Export PLY to XYZ text format with optional colors."""
        output_file = output_dir / f"{input_file.stem}.xyz"
        include_colors = opts.get('include_colors', False)
        delimiter = opts.get('delimiter', ' ')
        
        try:
            try:
                from plyfile import PlyData
                ply = PlyData.read(str(input_file))
                vertex = ply['vertex']
                has_colors = 'red' in vertex.data.dtype.names
                
                with open(output_file, 'w') as fout:
                    for i in range(len(vertex)):
                        data = vertex[i]
                        x, y, z = float(data['x']), float(data['y']), float(data['z'])
                        
                        if include_colors and has_colors:
                            r, g, b = int(data['red']), int(data['green']), int(data['blue'])
                            fout.write(f"{x}{delimiter}{y}{delimiter}{z}{delimiter}{r}{delimiter}{g}{delimiter}{b}\n")
                        else:
                            fout.write(f"{x}{delimiter}{y}{delimiter}{z}\n")
            except ImportError:
                # Fallback: parse manually
                with open(input_file, 'r') as fin:
                    lines = fin.readlines()

                with open(output_file, 'w') as fout:
                    in_header = True
                    has_colors = False
                    for line in lines:
                        if in_header:
                            if line.strip().startswith("end_header"):
                                in_header = False
                            if "property" in line and "red" in line:
                                has_colors = True
                            continue
                        parts = line.strip().split()
                        if len(parts) >= 3:
                            if include_colors and len(parts) >= 6:
                                fout.write(f"{parts[0]}{delimiter}{parts[1]}{delimiter}{parts[2]}{delimiter}{parts[3]}{delimiter}{parts[4]}{delimiter}{parts[5]}\n")
                            else:
                                fout.write(f"{parts[0]}{delimiter}{parts[1]}{delimiter}{parts[2]}\n")

            self.log(f"Exporté XYZ{' (avec couleurs)' if include_colors else ''}: {output_file}")
            return True
        except Exception as e:
            self.log(f"Erreur export XYZ: {e}")
            return False

    def _export_obj(self, input_file: Path, output_dir: Path, opts: dict) -> bool:
        """Export PLY to OBJ format (point cloud, no mesh)."""
        output_file = output_dir / f"{input_file.stem}.obj"
        include_mtl = opts.get('include_materials', True)
        include_colors = opts.get('include_vertex_colors', True)
        scale = opts.get('scale', 1.0)
        
        try:
            try:
                from plyfile import PlyData
                ply = PlyData.read(str(input_file))
                vertex = ply['vertex']
                has_colors = 'red' in vertex.data.dtype.names
                
                if include_mtl:
                    mtl_file = output_dir / f"{input_file.stem}.mtl"
                    with open(mtl_file, 'w') as fmtl:
                        fmtl.write("# Material\n")
                        fmtl.write("newmtl point_material\n")
                        fmtl.write("Ka 1.000 1.000 1.000\n")
                        fmtl.write("Kd 1.000 1.000 1.000\n")
                        fmtl.write("Ks 0.000 0.000 0.000\n")
                        fmtl.write("Ns 10.0\n")
                        fmtl.write("d 1.0\n")
                        fmtl.write("illum 1\n\n")

                with open(output_file, 'w') as fout:
                    fout.write("# Exported from CorbeauSplat\n")
                    if include_mtl:
                        fout.write(f"mtllib {input_file.stem}.mtl\n\n")
                    fout.write("o PointCloud\n\n")

                    vertex_count = 0
                    for i in range(len(vertex)):
                        data = vertex[i]
                        x = float(data['x']) * scale
                        y = float(data['y']) * scale
                        z = float(data['z']) * scale
                        
                        vertex_count += 1
                        if include_colors and has_colors:
                            r, g, b = int(data['red'])/255, int(data['green'])/255, int(data['blue'])/255
                            fout.write(f"v {x:.6f} {y:.6f} {z:.6f} {r:.3f} {g:.3f} {b:.3f}\n")
                        else:
                            fout.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")

                    fout.write(f"\n# {vertex_count} vertices\n")
                    
            except ImportError:
                # Fallback: parse manually
                with open(input_file, 'r') as fin:
                    lines = fin.readlines()

                has_colors = False
                in_header = True
                vertex_count = 0

                with open(output_file, 'w') as fout:
                    fout.write("# Exported from CorbeauSplat\n")
                    if include_mtl:
                        mtl_file = output_dir / f"{input_file.stem}.mtl"
                        with open(mtl_file, 'w') as fmtl:
                            fmtl.write("# Material\n")
                            fmtl.write("newmtl point_material\n")
                            fmtl.write("Ka 1.000 1.000 1.000\n")
                            fmtl.write("Kd 1.000 1.000 1.000\n")
                            fmtl.write("Ks 0.000 0.000 0.000\n")
                            fmtl.write("Ns 10.0\n")
                            fmtl.write("d 1.0\n")
                            fmtl.write("illum 1\n\n")
                        fout.write(f"mtllib {input_file.stem}.mtl\n\n")
                    fout.write("o PointCloud\n\n")

                    for line in lines:
                        if in_header:
                            if line.strip().startswith("end_header"):
                                in_header = False
                            if "property" in line and "red" in line:
                                has_colors = True
                            continue

                        parts = line.strip().split()
                        if len(parts) >= 3:
                            vertex_count += 1
                            x = float(parts[0]) * scale
                            y = float(parts[1]) * scale
                            z = float(parts[2]) * scale
                            if include_colors and len(parts) >= 6:
                                r, g, b = int(parts[3])/255, int(parts[4])/255, int(parts[5])/255
                                fout.write(f"v {x:.6f} {y:.6f} {z:.6f} {r:.3f} {g:.3f} {b:.3f}\n")
                            else:
                                fout.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")

                    fout.write(f"\n# {vertex_count} vertices\n")

            self.log(f"Exporté OBJ: {output_file}" + (f" + {mtl_file}" if include_mtl else ""))
            return True
        except Exception as e:
            self.log(f"Erreur export OBJ: {e}")
            return False

    def _export_glb(self, input_file: Path, output_dir: Path, opts: dict) -> bool:
        """Export PLY to GLB using available tools."""
        output_file = output_dir / f"{input_file.stem}.glb"
        method = opts.get('method', 'auto')  # auto, trimesh, open3d, assimp
        point_size = opts.get('point_size', 0.01)
        
        if method == 'auto':
            if self._try_export_glb_trimesh(input_file, output_file, opts):
                return True
            if self._try_export_glb_open3d(input_file, output_file, opts):
                return True
            if self._try_export_glb_assimp(input_file, output_file, opts):
                return True
        elif method == 'trimesh':
            if self._try_export_glb_trimesh(input_file, output_file, opts):
                return True
        elif method == 'open3d':
            if self._try_export_glb_open3d(input_file, output_file, opts):
                return True
        elif method == 'assimp':
            if self._try_export_glb_assimp(input_file, output_file, opts):
                return True

        self.log("GLB export failed. Install: pip install trimesh open3d")
        return False

    def _try_export_glb_trimesh(self, input_file: Path, output_file: Path, opts: dict) -> bool:
        """Export using trimesh library."""
        try:
            import trimesh
            import numpy as np
            from plyfile import PlyData
            
            ply = PlyData.read(str(input_file))
            vertex = ply['vertex']
            
            points = np.column_stack([
                vertex['x'], vertex['y'], vertex['z']
            ])
            
            colors = None
            if 'red' in vertex.data.dtype.names:
                colors = np.column_stack([
                    vertex['red'], vertex['green'], vertex['blue']
                ])
            
            # Create point cloud
            cloud = trimesh.PointCloud(vertices=points, colors=colors)
            
            # Export as GLB
            cloud.export(str(output_file))
            self.log(f"Exporté GLB via trimesh: {output_file}")
            return True
        except ImportError:
            return False
        except Exception as e:
            self.log(f"Erreur trimesh GLB: {e}")
            return False

    def _try_export_glb_open3d(self, input_file: Path, output_file: Path, opts: dict) -> bool:
        """Export using open3d library."""
        try:
            import open3d as o3d
            
            pcd = o3d.io.read_point_cloud(str(input_file))
            
            # open3d doesn't natively export GLB, convert via intermediate
            temp_ply = output_file.parent / f"{input_file.stem}_temp.ply"
            o3d.io.write_point_cloud(str(temp_ply), pcd)
            
            # Then use trimesh for GLB
            try:
                import trimesh
                scene = trimesh.load(str(temp_ply))
                scene.export(str(output_file))
                temp_ply.unlink(missing_ok=True)
                self.log(f"Exporté GLB via open3d+trimesh: {output_file}")
                return True
            except ImportError:
                pass
                
            temp_ply.unlink(missing_ok=True)
            return False
        except ImportError:
            return False
        except Exception as e:
            self.log(f"Erreur open3d GLB: {e}")
            return False

    def _try_export_glb_assimp(self, input_file: Path, output_file: Path, opts: dict) -> bool:
        """Export using assimp command-line tool via intermediate OBJ."""
        try:
            from plyfile import PlyData
            
            ply = PlyData.read(str(input_file))
            vertex = ply['vertex']
            
            temp_obj = input_file.parent / f"{input_file.stem}_temp.obj"
            temp_mtl = input_file.parent / f"{input_file.stem}_temp.mtl"

            with open(temp_obj, 'w') as f:
                f.write("# Temp OBJ from PLY\n")
                f.write(f"mtllib {temp_mtl.name}\n")
                f.write("o PointCloud\n\n")

                for i in range(len(vertex)):
                    data = vertex[i]
                    x, y, z = data['x'], data['y'], data['z']
                    if 'red' in data.dtype.names:
                        r, g, b = data['red']/255, data['green']/255, data['blue']/255
                        f.write(f"v {x} {y} {z} {r:.3f} {g:.3f} {b:.3f}\n")
                    else:
                        f.write(f"v {x} {y} {z}\n")

                f.write(f"\n# {len(vertex)} vertices\n")

            with open(temp_mtl, 'w') as f:
                f.write("newmtl point_material\n")
                f.write("Kd 1.0 1.0 1.0\n")

            if self._convert_obj_to_glb(temp_obj, output_file):
                temp_obj.unlink(missing_ok=True)
                temp_mtl.unlink(missing_ok=True)
                self.log(f"Exporté GLB via assimp: {output_file}")
                return True

            temp_obj.unlink(missing_ok=True)
            temp_mtl.unlink(missing_ok=True)
            return False
        except Exception as e:
            self.log(f"Erreur assimp GLB: {e}")
            return False

    def _export_spz(self, input_file: Path, output_dir: Path, opts: dict) -> bool:
        """Export PLY to SPZ (compressed Gaussian Splats format).

        SPZ format specification (v1):
        - Header: "SPZ\0" (4 bytes)
        - Version: uint32 (4 bytes) = 1
        - Num points: uint32 (4 bytes)
        - Positions: float32[3] per point (12 bytes each)
        - Colors: uint8[4] per point (rgba, 4 bytes each)
        - Scales: uint8[3] per point (log compressed, 3 bytes each)
        - Rotations: uint8[3] per point (octahedral compressed, 3 bytes each)
        - Alphas: uint8 per point (sigmoid compressed, 1 byte each)
        """
        output_file = output_dir / f"{input_file.stem}.spz"
        
        # Options
        quantize_positions = opts.get('quantize_positions', False)
        compression_level = opts.get('compression_level', 'normal')  # low, normal, high
        include_sh = opts.get('include_sh', True)  # Spherical harmonics

        try:
            # Try using plyfile first
            try:
                from plyfile import PlyData
                ply = PlyData.read(str(input_file))
                vertex = ply['vertex']
                num_points = len(vertex)

                # Extract data
                positions = []
                colors = []
                scales = []
                rotations = []
                alphas = []

                for i in range(num_points):
                    data = vertex[i]
                    # Positions (always present)
                    positions.extend([float(data['x']), float(data['y']), float(data['z'])])

                    # Colors (may not be present, default to gray)
                    if 'red' in data.dtype.names:
                        colors.extend([int(data['red']), int(data['green']), int(data['blue']), 255])
                    elif 'diffuse_red' in data.dtype.names:
                        colors.extend([int(data['diffuse_red']), int(data['diffuse_green']), int(data['diffuse_blue']), 255])
                    else:
                        colors.extend([128, 128, 128, 255])

                    # Scales (may not be present, default to small)
                    if 'scale_0' in data.dtype.names:
                        s0 = max(0.001, float(data.get('scale_0', -2.0)))
                        s1 = max(0.001, float(data.get('scale_1', -2.0)))
                        s2 = max(0.001, float(data.get('scale_2', -2.0)))
                        scales.extend(self._compress_scale(s0, s1, s2))
                    else:
                        scales.extend([0, 0, 0])

                    # Rotations (quaternions) - may not be present
                    if 'rot_0' in data.dtype.names:
                        r0 = float(data.get('rot_0', 1.0))
                        r1 = float(data.get('rot_1', 0.0))
                        r2 = float(data.get('rot_2', 0.0))
                        r3 = float(data.get('rot_3', 0.0))
                        # Normalize quaternion
                        norm = math.sqrt(r0*r0 + r1*r1 + r2*r2 + r3*r3)
                        if norm > 0:
                            r0, r1, r2, r3 = r0/norm, r1/norm, r2/norm, r3/norm
                        rotations.extend(self._compress_rotation(r0, r1, r2, r3))
                    else:
                        rotations.extend([127, 127, 127])  # Identity rotation

                    # Alphas (opacity) - may not be present, default to 1.0
                    if 'opacity' in data.dtype.names:
                        alpha = float(data['opacity'])
                        alphas.append(self._compress_alpha(alpha))
                    else:
                        alphas.append(255)  # Fully opaque

            except ImportError:
                # Fallback: parse PLY manually
                positions, colors, scales, rotations, alphas = self._parse_ply_manual(input_file)
                num_points = len(positions) // 3

            # Write SPZ file
            with open(output_file, 'wb') as f:
                # Header
                f.write(b'SPZ\x00')
                # Version
                f.write(struct.pack('<I', 1))
                # Num points
                f.write(struct.pack('<I', num_points))

                # Write data
                # Positions as float32
                f.write(struct.pack(f'<{len(positions)}f', *positions))
                # Colors as uint8
                f.write(bytes(colors))
                # Scales as uint8
                f.write(bytes(scales))
                # Rotations as uint8
                f.write(bytes(rotations))
                # Alphas as uint8
                f.write(bytes(alphas))

            self.log(f"Exporté SPZ: {output_file} ({num_points} points)")
            return True

        except Exception as e:
            self.log(f"Erreur export SPZ: {e}")
            return False

    def _compress_scale(self, s0: float, s1: float, s2: float) -> list:
        """Compress scale values using log encoding."""
        # Log scale encoding: store log(scale) with range [-10, 10]
        def encode(s):
            log_s = math.log(max(s, 1e-10))
            # Map [-10, 10] to [0, 255]
            val = int((log_s + 10) / 20 * 255)
            return max(0, min(255, val))
        return [encode(s0), encode(s1), encode(s2)]

    def _compress_rotation(self, r0: float, r1: float, r2: float, r3: float) -> list:
        """Compress quaternion using octahedral encoding."""
        # Convert quaternion to octahedral encoding
        # r0 is the scalar (w), r1-r3 are the vector (x,y,z)
        if r0 < 0:
            r0, r1, r2, r3 = -r0, -r1, -r2, -r3

        # Project to octahedron
        sum_abs = abs(r1) + abs(r2) + abs(r3)
        if sum_abs > 0:
            x = r1 / sum_abs
            y = r2 / sum_abs
            z = r3 / sum_abs
        else:
            x, y, z = 0, 0, 0

        # Octahedral projection
        if z >= 0:
            u = x
            v = y
        else:
            # Fold the bottom half
            u = (1 - abs(y)) * (1 if x >= 0 else -1)
            v = (1 - abs(x)) * (1 if y >= 0 else -1)

        # Map [-1, 1] to [0, 255]
        enc_u = int((u + 1) / 2 * 255)
        enc_v = int((v + 1) / 2 * 255)
        # Third component for z sign or precision
        enc_z = 255 if r3 >= 0 else 0

        return [max(0, min(255, enc_u)), max(0, min(255, enc_v)), enc_z]

    def _compress_alpha(self, alpha: float) -> int:
        """Compress alpha using sigmoid inverse encoding."""
        # alpha is typically in range [-10, 10] after inverse sigmoid
        # Map to [0, 255]
        val = int((alpha + 10) / 20 * 255)
        return max(0, min(255, val))

    def _parse_ply_manual(self, input_file: Path) -> tuple:
        """Parse PLY file manually without plyfile dependency."""
        positions = []
        colors = []
        scales = []
        rotations = []
        alphas = []

        with open(input_file, 'rb') as f:
            # Read header
            header_lines = []
            while True:
                line = f.readline().decode('ascii').strip()
                header_lines.append(line)
                if line == "end_header":
                    break

            # Parse header to find properties
            has_colors = any("property" in line and "red" in line for line in header_lines)
            has_scales = any("property" in line and "scale_0" in line for line in header_lines)
            has_rots = any("property" in line and "rot_0" in line for line in header_lines)
            has_alpha = any("property" in line and "opacity" in line for line in header_lines)

            # Read binary data
            import numpy as np

            # Try to determine format
            format_line = [l for l in header_lines if l.startswith("format")]
            is_binary = len(format_line) > 0 and "binary" in format_line[0]

            if is_binary:
                # Count vertex properties
                vertex_props = []
                in_element = False
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

                # Read vertex data
                dtype_map = {
                    'float': '<f4', 'float32': '<f4', 'float64': '<f8',
                    'uchar': '<u1', 'uint8': '<u1',
                    'char': '<i1', 'int8': '<i1',
                    'ushort': '<u2', 'uint16': '<u2',
                    'short': '<i2', 'int16': '<i2',
                    'uint': '<u4', 'uint32': '<u4',
                    'int': '<i4', 'int32': '<i4'
                }

                # Create dtype for structured array
                np_dtypes = []
                for dtype, name in vertex_props:
                    base_type = dtype.split('_')[0] if '_' in dtype else dtype
                    np_dtype = dtype_map.get(base_type, '<f4')
                    np_dtypes.append((name, np_dtype))

                if np_dtypes:
                    data = np.fromfile(f, dtype=np_dtypes, count=num_vertices)

                    for i in range(num_vertices):
                        row = data[i]
                        # Positions
                        positions.extend([float(row['x']), float(row['y']), float(row['z'])])

                        # Colors
                        if has_colors:
                            colors.extend([int(row['red']), int(row['green']), int(row['blue']), 255])
                        else:
                            colors.extend([128, 128, 128, 255])

                        # Scales
                        if has_scales:
                            s0 = max(0.001, float(row['scale_0']))
                            s1 = max(0.001, float(row['scale_1']))
                            s2 = max(0.001, float(row['scale_2']))
                            scales.extend(self._compress_scale(s0, s1, s2))
                        else:
                            scales.extend([0, 0, 0])

                        # Rotations
                        if has_rots:
                            r0 = float(row['rot_0'])
                            r1 = float(row['rot_1'])
                            r2 = float(row['rot_2'])
                            r3 = float(row['rot_3'])
                            norm = math.sqrt(r0*r0 + r1*r1 + r2*r2 + r3*r3)
                            if norm > 0:
                                r0, r1, r2, r3 = r0/norm, r1/norm, r2/norm, r3/norm
                            rotations.extend(self._compress_rotation(r0, r1, r2, r3))
                        else:
                            rotations.extend([127, 127, 127])

                        # Alphas
                        if has_alpha:
                            alphas.append(self._compress_alpha(float(row['opacity'])))
                        else:
                            alphas.append(255)
            else:
                # ASCII format - read line by line
                for line in f:
                    parts = line.decode('ascii').strip().split()
                    if len(parts) >= 3:
                        positions.extend([float(parts[0]), float(parts[1]), float(parts[2])])

                        if has_colors and len(parts) >= 6:
                            colors.extend([int(parts[3]), int(parts[4]), int(parts[5]), 255])
                        else:
                            colors.extend([128, 128, 128, 255])

                        scales.extend([0, 0, 0])
                        rotations.extend([127, 127, 127])
                        alphas.append(255)

        return positions, colors, scales, rotations, alphas

    def _convert_obj_to_glb(self, obj_file: Path, glb_file: Path) -> bool:
        """Convert OBJ to GLB using assimp or blender."""
        assimp = shutil.which("assimp")
        if assimp:
            try:
                subprocess.run(
                    [assimp, "export", str(obj_file), str(glb_file)],
                    capture_output=True, check=True
                )
                return True
            except Exception:
                pass

        blender = shutil.which("blender")
        if blender:
            import json
            import tempfile
            tmp_path = None
            blender_script = (
                "import bpy, json\n"
                f"paths = {json.dumps({'obj': str(obj_file), 'glb': str(glb_file)})}\n"
                "bpy.ops.import_scene.obj(filepath=paths['obj'])\n"
                "bpy.ops.export_scene.gltf(filepath=paths['glb'])\n"
            )
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
                    tf.write(blender_script)
                    tmp_path = tf.name
                subprocess.run(
                    [blender, "--background", "--python", tmp_path],
                    capture_output=True, check=True, timeout=60
                )
                return True
            except Exception as e:
                self.log(f"Blender export failed: {e}")
            finally:
                if tmp_path:
                    Path(tmp_path).unlink(missing_ok=True)

        return False