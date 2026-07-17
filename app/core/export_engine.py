import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from .base_engine import BaseEngine


class ExportEngine(BaseEngine):
    """Engine for exporting PLY files to various formats."""

    SUPPORTED_FORMATS = ["spz", "glb", "obj", "ply", "xyz"]

    def __init__(self, logger_callback: Callable | None = None) -> None:
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
        options: dict | None = None,
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
                with open(input_file, 'rb') as f_in, gzip.open(output_file, 'wb') as f_out:
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
                with open(input_file) as fin:
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
                with open(input_file) as fin:
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
        opts.get('point_size', 0.01)

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
            import numpy as np
            import trimesh
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
        """Export PLY to SPZ using the official nianticlabs/spz library.

        Requires the 'spz' package (compiled from source via the SPZ installer).
        PLY coordinate system is assumed RDF (Right-Down-Forward), which is the
        standard output of Brush/COLMAP pipelines. The library converts internally
        to its own storage format when writing.

        No fallback: if 'spz' is not installed the export fails with a clear message.
        """
        output_file = output_dir / f"{input_file.stem}.spz"

        try:
            import spz
        except ImportError:
            self.log(
                "Erreur export SPZ: la bibliothèque 'spz' (nianticlabs/spz) n'est pas installée. "
                "Relancez l'installateur de dépendances (setup_dependencies.py) pour la compiler."
            )
            return False

        try:
            # load_splat_from_ply handles all PLY field mapping internally
            # (positions, scales in log-space, rotations wxyz→internal, SH bands, etc.)
            unpack_opts = spz.UnpackOptions()
            cloud = spz.load_splat_from_ply(str(input_file), unpack_opts)

            # PLY from Brush/COLMAP is in RDF (Right-Down-Forward = OpenCV convention)
            pack_opts = spz.PackOptions()
            pack_opts.from_coord = spz.CoordinateSystem.RDF

            ok = spz.save_spz(cloud, pack_opts, str(output_file))
            if not ok:
                self.log("Erreur export SPZ: save_spz a retourné False")
                return False

            self.log(f"Exporté SPZ: {output_file} ({cloud.num_points} points)")
            return True

        except Exception as e:
            self.log(f"Erreur export SPZ: {e}")
            return False

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
            except Exception as e:
                self.log(f"Assimp export failed: {e}")

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
