"""STEP export of the assembled bed (one named solid per part copy)."""
import numpy as np
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.gp import gp_Pnt, gp_Vec
from OCP.IFSelect import IFSelect_RetDone
from OCP.Interface import Interface_Static
from OCP.Message import Message, Message_PrinterOStream
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from shapely import affinity
from shapely.geometry.polygon import orient


def _wire(points):
    poly = BRepBuilderAPI_MakePolygon()
    for x, y, z in points[:-1]:  # ring repeats its first point
        poly.Add(gp_Pnt(float(x), float(y), float(z)))
    poly.Close()
    return poly.Wire()


def _solid(shape, pl, thickness):
    shape = orient(shape)
    outer = pl.to_world(np.asarray(shape.exterior.coords), 0)
    mk = BRepBuilderAPI_MakeFace(_wire(outer), True)
    for ring in shape.interiors:
        inner = _wire(pl.to_world(np.asarray(ring.coords), 0))
        inner.Reverse()
        mk.Add(inner)
    n = np.asarray(pl.n, float) * thickness
    return BRepPrimAPI_MakePrism(mk.Face(), gp_Vec(*map(float, n))).Shape()


def write_step(parts, thickness, path, inches=True):
    doc = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
    tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    scale = 25.4 if inches else 1.0  # STEP is written in millimetres
    counts = {}
    for part in parts:
        t = getattr(part, "render_thickness", thickness)
        for pl in part.placements:
            scaled = type(pl)(tuple(np.asarray(pl.origin) * scale), pl.u, pl.v, pl.n)
            shp = affinity.scale(part.shape.simplify(0.01), scale, scale, origin=(0, 0))
            solid = _solid(shp, scaled, t * scale)
            for g, depth, _ in part.pockets:
                g = affinity.scale(g.simplify(0.005), scale, scale, origin=(0, 0))
                for piece in getattr(g, "geoms", [g]):
                    solid = BRepAlgoAPI_Cut(solid, _solid(piece, scaled, depth * scale)).Shape()
            counts[part.name] = counts.get(part.name, 0) + 1
            label = tool.AddShape(solid, False)
            name = part.name if part.qty == 1 else f"{part.name} {counts[part.name]}"
            TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
    Message.DefaultMessenger_s().RemovePrinters(Message_PrinterOStream.get_type_descriptor_s())
    Interface_Static.SetCVal_s("write.step.unit", "MM")
    writer = STEPCAFControl_Writer()
    writer.SetNameMode(True)
    writer.Transfer(doc, STEPControl_AsIs)
    if writer.Write(path) != IFSelect_RetDone:
        raise RuntimeError(f"STEP export failed: {path}")
