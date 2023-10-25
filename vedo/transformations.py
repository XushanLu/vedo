#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np

import vedo.vtkclasses as vtk

__docformat__ = "google"

__doc__ = """
Submodule to work with transformations <br>

![](https://vedo.embl.es/images/feats/transforms.png)
"""

__all__ = [
    "LinearTransform",
    "NonLinearTransform",
    "spher2cart",
    "cart2spher",
    "cart2cyl",
    "cyl2cart",
    "cyl2spher",
    "spher2cyl",
    "cart2pol",
    "pol2cart",
]

###################################################
def _is_sequence(arg):
    if hasattr(arg, "strip"):
        return False
    if hasattr(arg, "__getslice__"):
        return True
    if hasattr(arg, "__iter__"):
        return True
    return False


###################################################
class LinearTransform:
    """Work with linear transformations."""

    def __init__(self, T=None):
        """
        Define a linear transformation.
        Can be saved to file and reloaded.
        
        Arguments:
            T : (vtk.vtkTransform, numpy array)
                vtk transformation. Defaults to None.
        
        Example:
            ```python
            from vedo import *
            settings.use_parallel_projection = True

            LT = LinearTransform()
            LT.translate([3,0,1]).rotate_z(45)
            print(LT)

            sph = Sphere(r=0.2)
            print("Sphere before", s1.transform)
            s1.apply_transform(LT)
            # same as:
            # LT.apply_to(s1)
            print("Sphere after ", s1.transform)

            zero = Point([0,0,0])
            show(s1, zero, axes=1).close()
            ```
       """

        self.name = "LinearTransform"
        self.comment = ""

        if T is None:
            T = vtk.vtkTransform()

        elif isinstance(T, vtk.vtkMatrix4x4):
            S = vtk.vtkTransform()
            S.SetMatrix(T)
            T = S

        elif isinstance(T, vtk.vtkLandmarkTransform):
            S = vtk.vtkTransform()
            S.SetMatrix(T.GetMatrix())
            T = S

        elif _is_sequence(T):
            S = vtk.vtkTransform()
            M = vtk.vtkMatrix4x4()
            n = len(T)
            for i in range(n):
                for j in range(n):
                    M.SetElement(i, j, T[i][j])
            S.SetMatrix(M)
            T = S

        elif isinstance(T, vtk.vtkLinearTransform):
            S = vtk.vtkTransform()
            S.DeepCopy(T)
            T = S

        elif isinstance(T, LinearTransform):
            S = vtk.vtkTransform()
            S.DeepCopy(T.T)
            T = S
        
        elif isinstance(T, str):
            import json
            with open(T, "r") as read_file:
                D = json.load(read_file)
            self.name = D["name"]
            self.comment = D["comment"]
            matrix = np.array(D["matrix"])
            T = vtk.vtkTransform()
            m = vtk.vtkMatrix4x4()
            for i in range(4):
                for j in range(4):
                    m.SetElement(i, j, matrix[i][j])
            T.SetMatrix(m)

        self.T = T
        self.T.PostMultiply()
        self.inverse_flag = False

    def __str__(self):
        s = "Transformation Matrix 4x4:\n"
        s += str(self.matrix)
        s += f"\n({self.n_concatenated_transforms} concatenated transforms)"
        return s

    def __repr__(self):
        return self.__str__()

    def apply_to(self, obj):
        """Apply transformation."""
        if _is_sequence(obj):
            v = self.T.TransformFloatPoint(obj)
            return np.array(v)

        obj.transform = self

        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        if np.allclose(M - np.eye(4), 0):
            return

        tp = vtk.vtkTransformPolyDataFilter()
        tp.SetTransform(self.T)
        tp.SetInputData(obj.dataset)
        tp.Update()
        out = tp.GetOutput()

        obj.dataset.DeepCopy(out)
        obj.point_locator = None
        obj.cell_locator = None
        obj.line_locator = None

    def reset(self):
        """Reset transformation."""
        self.T.Identity()
        return self

    def pop(self):
        """Delete the transformation on the top of the stack 
        and sets the top to the next transformation on the stack."""
        self.T.Pop()
        return self

    def is_identity(self):
        """Check if identity."""
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        if np.allclose(M - np.eye(4), 0):
            return True
        return False

    def invert(self):
        """Invert transformation."""
        self.T.Inverse()
        self.inverse_flag = bool(self.T.GetInverseFlag())
        return self

    def compute_inverse(self):
        """Compute inverse."""
        t = self.clone()
        t.invert()
        return t

    def clone(self):
        """Clone transformation to make an exact copy."""
        return LinearTransform(self.T)

    def concatenate(self, T, pre_multiply=False):
        """
        Post-multiply (by default) 2 transfomations.
        
        Example:
            ```python
            from vedo import *

            A = LinearTransform()
            A.rotate_x(45)
            A.translate([7,8,9])
            A.translate([10,10,10])
            print("A", A)

            B = A.compute_inverse()
            B.shift([1,2,3])

            # A is applied first, then B
            print("A.concatenate(B)", A.concatenate(B))

            # B is applied first, then A
            # print("B*A", B*A)
            ```
        """
        if pre_multiply:
            self.T.PreMultiply()
        try:
            self.T.Concatenate(T)
        except:
            self.T.Concatenate(T.T)
        self.T.PostMultiply()
        return self
    
    def __mul__(self, A):
        """Pre-multiply 2 transfomations."""
        return self.concatenate(A, pre_multiply=True)

    def get_concatenated_transform(self, i):
        """Get intermediate matrix by concatenation index."""
        return LinearTransform(self.T.GetConcatenatedTransform(i))

    @property
    def n_concatenated_transforms(self):
        """Get number of concatenated transforms."""
        return self.T.GetNumberOfConcatenatedTransforms()

    def translate(self, *p):
        """Translate, same as `shift`."""
        self.T.Translate(*p)
        return self

    def shift(self, *p):
        """Shift, same as `translate`."""
        return self.translate(*p)

    def scale(self, s, origin=True):
        """Scale."""
        if not _is_sequence(s):
            s = [s, s, s]

        if origin is True:
            p = np.array(self.T.GetPosition())
            if np.linalg.norm(p) > 0:
                self.T.Translate(-p)
                self.T.Scale(*s)
                self.T.Translate(p)
            else:
                self.T.Scale(*s)

        elif _is_sequence(origin):
            origin = np.asarray(origin)
            self.T.Translate(-origin)
            self.T.Scale(*s)
            self.T.Translate(origin)

        else:
            self.T.Scale(*s)
        return self

    def rotate(self, angle, axis=(1, 0, 0), point=(0, 0, 0), rad=False):
        """
        Rotate around an arbitrary `axis` passing through `point`.

        Example:
            ```python
            from vedo import *
            c1 = Cube()
            c2 = c1.clone().c('violet').alpha(0.5) # copy of c1
            v = vector(0.2,1,0)
            p = vector(1,0,0)  # axis passes through this point
            c2.rotate(90, axis=v, point=p)
            l = Line(-v+p, v+p).lw(3).c('red')
            show(c1, l, c2, axes=1).close()
            ```
            ![](https://vedo.embl.es/images/feats/rotate_axis.png)
        """
        if rad:
            anglerad = angle
        else:
            anglerad = np.deg2rad(angle)
        axis = np.asarray(axis) / np.linalg.norm(axis)
        a = np.cos(anglerad / 2)
        b, c, d = -axis * np.sin(anglerad / 2)
        aa, bb, cc, dd = a * a, b * b, c * c, d * d
        bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
        R = np.array(
            [
                [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
            ]
        )
        rv = np.dot(R, self.T.GetPosition() - np.asarray(point)) + point

        if rad:
            angle *= 180.0 / np.pi
        # this vtk method only rotates in the origin of the object:
        self.T.RotateWXYZ(angle, axis[0], axis[1], axis[2])
        self.T.Translate(rv - np.array(self.T.GetPosition()))
        return self

    def _rotatexyz(self, axe, angle, rad, around):
        if rad:
            angle *= 180 / np.pi

        rot = dict(x=self.T.RotateX, y=self.T.RotateY, z=self.T.RotateZ)

        if around is None:
            # rotate around its origin
            rot[axe](angle)
        else:
            # displacement needed to bring it back to the origin
            self.T.Translate(-np.asarray(around))
            rot[axe](angle)
            self.T.Translate(around)
        return self

    def rotate_x(self, angle, rad=False, around=None):
        """
        Rotate around x-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("x", angle, rad, around)

    def rotate_y(self, angle, rad=False, around=None):
        """
        Rotate around y-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("y", angle, rad, around)

    def rotate_z(self, angle, rad=False, around=None):
        """
        Rotate around z-axis. If angle is in radians set `rad=True`.

        Use `around` to define a pivoting point.
        """
        return self._rotatexyz("z", angle, rad, around)

    def set_position(self, p):
        """Set position."""
        if len(p) == 2:
            p = np.array([p[0], p[1], 0])
        q = np.array(self.T.GetPosition())
        self.T.Translate(p - q)
        return self

    # def set_scale(self, s):
    #     """Set absolute scale."""
    #     if not _is_sequence(s):
    #         s = [s, s, s]
    #     s0, s1, s2 = 1, 1, 1
    #     b = self.T.GetScale()
    #     print(b)
    #     if b[0]:
    #         s0 = s[0] / b[0]
    #     if b[1]:
    #         s1 = s[1] / b[1]
    #     if b[2]:
    #         s2 = s[2] / b[2]
    #     self.T.Scale(s0, s1, s2)
    #     print()
    #     return self

    def get_scale(self):
        """Get current scale."""
        return np.array(self.T.GetScale())

    @property
    def orientation(self):
        """Compute orientation."""
        return np.array(self.T.GetOrientation())

    @property
    def position(self):
        """Compute position."""
        return np.array(self.T.GetPosition())

    @property
    def matrix(self):
        """Get trasformation matrix."""
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        return np.array(M)

    @matrix.setter
    def matrix(self, M):
        """Set trasformation by assigning a 4x4 or 3x3 numpy matrix."""
        m = vtk.vtkMatrix4x4()
        n = len(M)
        for i in range(n):
            for j in range(n):
                m.SetElement(i, j, M[i][j])
        self.T.SetMatrix(m)

    @property
    def matrix3x3(self):
        """Get matrix."""
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(3)] for i in range(3)]
        return np.array(M)

    def write(self, filename):  # eg. filename="transform.mat"
        """Save transformation to ASCII file."""
        import json
        m = self.T.GetMatrix()
        M = [[m.GetElement(i, j) for j in range(4)] for i in range(4)]
        arr = np.array(M)
        dictionary = {
            "name": self.name,
            "comment": self.comment,
            "matrix": arr.astype(float).tolist(),
            "n_concatenated_transforms": self.n_concatenated_transforms,
        }
        with open(filename, "w") as outfile:
            json.dump(dictionary, outfile, sort_keys=True, indent=2)

    def reorient(
        self, initaxis, newaxis, around=(0, 0, 0), rotation=0, rad=False, xyplane=True
    ):
        """
        Set/Get object orientation.

        Arguments:
            rotation : (float)
                rotate object around newaxis.
            concatenate : (bool)
                concatenate the orientation operation with the previous existing transform (if any)
            rad : (bool)
                set to True if angle is expressed in radians.
            xyplane : (bool)
                make an extra rotation to keep the object aligned to the xy-plane

        Example:
            ```python
            from vedo import *
            center = np.array([581/2,723/2,0])
            objs = []
            for a in np.linspace(0, 6.28, 7):
                v = vector(cos(a), sin(a), 0)*1000
                pic = Image(dataurl+"images/dog.jpg").rotate_z(10)
                pic.reorient([0,0,1], v)
                pic.pos(v - center)
                objs += [pic, Arrow(v, v+v)]
            show(objs, Point(), axes=1).close()
            ```
            ![](https://vedo.embl.es/images/feats/orientation.png)
        """
        newaxis  = np.asarray(newaxis) / np.linalg.norm(newaxis)
        initaxis = np.asarray(initaxis) / np.linalg.norm(initaxis)

        if not np.any(initaxis - newaxis):
            return self

        if not np.any(initaxis + newaxis):
            print("Warning: in reorient() initaxis and newaxis are parallel")
            newaxis += np.array([0.0000001, 0.0000002, 0])
            angleth = np.pi
        else:
            angleth = np.arccos(np.dot(initaxis, newaxis))
        crossvec = np.cross(initaxis, newaxis)

        p = np.asarray(around)
        self.T.Translate(-p)
        if rotation:
            if rad:
                rotation = np.rad2deg(rotation)
            self.T.RotateWXYZ(rotation, initaxis)

        self.T.RotateWXYZ(np.rad2deg(angleth), crossvec)

        if xyplane:
            self.T.RotateWXYZ(-self.orientation[0] * 1.4142, newaxis)

        self.T.Translate(p)
        return self


###################################################
class NonLinearTransform:
    """Work with non-linear transformations."""
    
    def __init__(self, T=None):

        self.name = "NonLinearTransform"
        self.filename = ""
        self.comment = ""

        if T is None:
            T = vtk.vtkThinPlateSplineTransform()

        elif isinstance(T, vtk.vtkThinPlateSplineTransform):
            S = vtk.vtkThinPlateSplineTransform()
            S.DeepCopy(T)
            T = S

        elif isinstance(T, NonLinearTransform):
            S = vtk.vtkThinPlateSplineTransform()
            S.DeepCopy(T.T)
            T = S

        elif isinstance(T, str):
            import json
            filename = str(T)
            self.filename = filename
            with open(filename, "r") as read_file:
                D = json.load(read_file)
            self.name = D["name"]
            self.comment = D["comment"]
            source = D["source_points"]
            target = D["target_points"]
            mode = D["mode"]
            sigma = D["sigma"]

            T = vtk.vtkThinPlateSplineTransform()
            vptss = vtk.vtkPoints()
            for p in source:
                vptss.InsertNextPoint(p[0], p[1], p[2])
            T.SetSourceLandmarks(vptss)
            vptst = vtk.vtkPoints()
            for p in target:
                vptst.InsertNextPoint(p[0], p[1], p[2])
            T.SetTargetLandmarks(vptst)
            T.SetSigma(sigma)
            # mode
            if mode == "2d":
                T.SetBasisToR2LogR()
            elif mode == "3d":
                T.SetBasisToR()
            else:
                print(f'In {filename} mode can be either "2d" or "3d"')

        self.T = T
        self.inverse_flag = False


    @property
    def position(self):
        """
        Trying to get the position of a `NonLinearTransform` always returns [0,0,0].
        """
        return np.array([0.0, 0.0, 0.0], dtype=np.float32)
    
    @position.setter
    def position(self, p):
        """
        Trying to set position of a `NonLinearTransform` 
        has no effect and prints a warning.

        Use clone() method to create a copy of the object,
        or reset it with 'object.transform = vedo.LinearTransform()'
        """
        print("Warning: NonLinearTransform has no position.")
        print("  Use clone() method to create a copy of the object,")
        print("  or reset it with 'object.transform = vedo.LinearTransform()'")

    @property
    def source_points(self):
        """Get the source points."""
        pts = self.T.GetSourceLandmarks()
        vpts = []
        for i in range(pts.GetNumberOfPoints()):
            vpts.append(pts.GetPoint(i))
        return np.array(vpts, dtype=np.float32)
    
    @property
    def target_points(self):
        """Get the target points."""
        pts = self.T.GetTargetLandmarks()
        vpts = []
        for i in range(pts.GetNumberOfPoints()):
            vpts.append(pts.GetPoint(i))
        return np.array(vpts, dtype=np.float32)
 
    @source_points.setter
    def source_points(self, pts):
        """Set source points."""
        if _is_sequence(pts):
            pass
        else:
            pts = pts.vertices
        vpts = vtk.vtkPoints()
        for p in pts:
            vpts.InsertNextPoint(p[0], p[1], p[2])
        self.T.SetSourceLandmarks(vpts)
    
    @target_points.setter
    def target_points(self, pts):
        """Set target points."""
        if _is_sequence(pts):
            pass
        else:
            pts = pts.vertices
        vpts = vtk.vtkPoints()
        for p in pts:
            vpts.InsertNextPoint(p[0], p[1], p[2])
        self.T.SetTargetLandmarks(vpts)
       
    @property
    def sigma(self) -> float:
        """Set sigma."""
        return self.T.GetSigma()

    @sigma.setter
    def sigma(self, s):
        """Get sigma."""
        self.T.SetSigma(s)

    @property
    def mode(self) -> str:
        """Get mode."""
        m = self.T.GetBasis()
        if m == 0:
            return "2d"
        elif m == 1:
            return "3d"

    @mode.setter
    def mode(self, m):
        """Set mode."""
        if m=='3d':
            self.T.SetBasisToR()
        elif m=='2d':
            self.T.SetBasisToR2LogR()
        else:
            print('In NonLinearTransform mode can be either "2d" or "3d"')

    def clone(self):
        """Clone transformation to make an exact copy."""
        return NonLinearTransform(self.T)
        
    def write(self, filename):
        """Save transformation to ASCII file."""
        import json
        dictionary = {
            "name": self.name,
            "comment": self.comment,
            "mode": self.mode,
            "sigma": self.sigma,
            "source_points": self.source_points.astype(float).tolist(),
            "target_points": self.target_points.astype(float).tolist(),
        }
        with open(filename, "w") as outfile:
            json.dump(dictionary, outfile, sort_keys=True, indent=2)
        
    def invert(self):
        """Invert transformation."""
        self.T.Inverse()
        self.inverse_flag = bool(self.T.GetInverseFlag())
        return self
    
    def compute_inverse(self):
        """Compute inverse."""
        t = self.clone()
        t.invert()
        return t   
    
    def apply_to(self, obj):
        """Apply transformation."""
        if _is_sequence(obj):
            v = self.T.TransformFloatPoint(obj)
            return np.array(v)

        obj.transform = self

        tp = vtk.vtkTransformPolyDataFilter()
        tp.SetTransform(self.T)
        tp.SetInputData(obj.dataset)
        tp.Update()
        out = tp.GetOutput()

        obj.dataset.DeepCopy(out)
        obj.point_locator = None
        obj.cell_locator = None
        obj.line_locator = None
     

########################################################################
# 2d ######
def cart2pol(x, y):
    """2D Cartesian to Polar coordinates conversion."""
    theta = np.arctan2(y, x)
    rho = np.hypot(x, y)
    return np.array([rho, theta])


def pol2cart(rho, theta):
    """2D Polar to Cartesian coordinates conversion."""
    x = rho * np.cos(theta)
    y = rho * np.sin(theta)
    return np.array([x, y])


########################################################################
# 3d ######
def cart2spher(x, y, z):
    """3D Cartesian to Spherical coordinate conversion."""
    hxy = np.hypot(x, y)
    rho = np.hypot(hxy, z)
    theta = np.arctan2(hxy, z)
    phi = np.arctan2(y, x)
    return np.array([rho, theta, phi])


def spher2cart(rho, theta, phi):
    """3D Spherical to Cartesian coordinate conversion."""
    st = np.sin(theta)
    sp = np.sin(phi)
    ct = np.cos(theta)
    cp = np.cos(phi)
    rst = rho * st
    x = rst * cp
    y = rst * sp
    z = rho * ct
    return np.array([x, y, z])


def cart2cyl(x, y, z):
    """3D Cartesian to Cylindrical coordinate conversion."""
    rho = np.sqrt(x * x + y * y)
    theta = np.arctan2(y, x)
    return np.array([rho, theta, z])


def cyl2cart(rho, theta, z):
    """3D Cylindrical to Cartesian coordinate conversion."""
    x = rho * np.cos(theta)
    y = rho * np.sin(theta)
    return np.array([x, y, z])


def cyl2spher(rho, theta, z):
    """3D Cylindrical to Spherical coordinate conversion."""
    rhos = np.sqrt(rho * rho + z * z)
    phi = np.arctan2(rho, z)
    return np.array([rhos, phi, theta])


def spher2cyl(rho, theta, phi):
    """3D Spherical to Cylindrical coordinate conversion."""
    rhoc = rho * np.sin(theta)
    z = rho * np.cos(theta)
    return np.array([rhoc, phi, z])
