"""Parametric building with real floor plans, wall thickness, and interiors."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for block in list(coll):
            if getattr(block, "users", 1) == 0:
                coll.remove(block)


def mat(name, color, roughness=0.55, metallic=0.0, transmission=0.0, emission=None, emit=0.0):
    material = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        for key in ("Transmission Weight", "Transmission"):
            if key in bsdf.inputs and transmission:
                bsdf.inputs[key].default_value = transmission
                break
        if emission and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emit
    material.diffuse_color = (*color, 1.0)
    return material


EXTERIOR = {
    "mass_timber": (0.55, 0.34, 0.16),
    "brick": (0.52, 0.22, 0.16),
    "recycled_steel": (0.38, 0.44, 0.48),
    "rammed_earth": (0.62, 0.42, 0.24),
    "concrete": (0.48, 0.46, 0.42),
}

# Interior walls follow the structure — never gallery-white plaster.
INTERIOR = {
    "mass_timber": (0.58, 0.38, 0.18),
    "brick": (0.66, 0.42, 0.28),
    "recycled_steel": (0.42, 0.50, 0.56),
    "rammed_earth": (0.60, 0.40, 0.22),
    "concrete": (0.50, 0.46, 0.40),
}

CANOPY = [
    (0.14, 0.38, 0.12),
    (0.20, 0.46, 0.14),
    (0.10, 0.30, 0.10),
    (0.24, 0.42, 0.16),
]


def ensure_collection(name):
    col = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    return col


def box(name, location, size, material, collection, cutaway=False):
    mesh = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    verts = [
        (-sx, -sy, -sz),
        (sx, -sy, -sz),
        (sx, sy, -sz),
        (-sx, sy, -sz),
        (-sx, -sy, sz),
        (sx, -sy, sz),
        (sx, sy, sz),
        (-sx, sy, sz),
    ]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(("CUTAWAY_" + name) if cutaway else name, mesh)
    obj.location = location
    obj.data.materials.append(material)
    collection.objects.link(obj)
    return obj


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def add_camera(name, location, target, lens=32):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    cam = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = location
    look_at(cam, target)
    return cam


def add_point_light(name, location, energy, collection, size=0.4):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    collection.objects.link(obj)
    return obj


def wall_span(name, axis, a, b, fixed, z0, z1, thick, material, collection, cutaway=False):
    length, height = b - a, z1 - z0
    if length < 0.04 or height < 0.04:
        return None
    mid, z = (a + b) / 2, (z0 + z1) / 2
    if axis == "x":
        loc, size = (mid, fixed, z), (length, thick, height)
    else:
        loc, size = (fixed, mid, z), (thick, length, height)
    return box(name, loc, size, material, collection, cutaway=cutaway)


def fill_window(name, axis, a, b, fixed, z0, sill, head, thick, frame, glass, collection, cutaway=False):
    z_sill, z_head = z0 + sill, z0 + head
    inset = 0.04
    t = max(0.06, thick * 0.35)
    if axis == "x":
        y = fixed
        box(f"{name}_sill", ((a + b) / 2, y, z_sill + 0.03), (b - a, thick + 0.08, 0.06), frame, collection, cutaway)
        box(f"{name}_head", ((a + b) / 2, y, z_head - 0.03), (b - a, thick + 0.04, 0.06), frame, collection, cutaway)
        box(f"{name}_L", (a + 0.04, y, (z_sill + z_head) / 2), (0.07, t, head - sill), frame, collection, cutaway)
        box(f"{name}_R", (b - 0.04, y, (z_sill + z_head) / 2), (0.07, t, head - sill), frame, collection, cutaway)
        box(
            f"{name}_glass",
            ((a + b) / 2, y, (z_sill + z_head) / 2),
            (b - a - 0.12, 0.02, head - sill - 0.12),
            glass,
            collection,
            cutaway,
        )
        # mullion
        box(f"{name}_mull", ((a + b) / 2, y, (z_sill + z_head) / 2), (0.04, t, head - sill - 0.08), frame, collection, cutaway)
    else:
        x = fixed
        box(f"{name}_sill", (x, (a + b) / 2, z_sill + 0.03), (thick + 0.08, b - a, 0.06), frame, collection, cutaway)
        box(f"{name}_head", (x, (a + b) / 2, z_head - 0.03), (thick + 0.04, b - a, 0.06), frame, collection, cutaway)
        box(f"{name}_L", (x, a + 0.04, (z_sill + z_head) / 2), (t, 0.07, head - sill), frame, collection, cutaway)
        box(f"{name}_R", (x, b - 0.04, (z_sill + z_head) / 2), (t, 0.07, head - sill), frame, collection, cutaway)
        box(
            f"{name}_glass",
            (x, (a + b) / 2, (z_sill + z_head) / 2),
            (0.02, b - a - 0.12, head - sill - 0.12),
            glass,
            collection,
            cutaway,
        )


def fill_door(name, axis, a, b, fixed, z0, head, thick, frame, leaf, collection, cutaway=False, interior=False):
    z_head = z0 + head
    if axis == "x":
        y = fixed
        box(f"{name}_jambL", (a + 0.04, y, z0 + head / 2), (0.07, thick * 0.5, head), frame, collection, cutaway)
        box(f"{name}_jambR", (b - 0.04, y, z0 + head / 2), (0.07, thick * 0.5, head), frame, collection, cutaway)
        box(f"{name}_lintel", ((a + b) / 2, y, z_head - 0.04), (b - a, thick * 0.5, 0.08), frame, collection, cutaway)
        door_y = y + (0.03 if interior else -0.02)
        box(f"{name}_leaf", ((a + b) / 2, door_y, z0 + head / 2 - 0.02), (b - a - 0.12, 0.04, head - 0.1), leaf, collection, cutaway)
    else:
        x = fixed
        box(f"{name}_jambL", (x, a + 0.04, z0 + head / 2), (thick * 0.5, 0.07, head), frame, collection, cutaway)
        box(f"{name}_jambR", (x, b - 0.04, z0 + head / 2), (thick * 0.5, 0.07, head), frame, collection, cutaway)
        box(f"{name}_lintel", (x, (a + b) / 2, z_head - 0.04), (thick * 0.5, b - a, 0.08), frame, collection, cutaway)
        box(f"{name}_leaf", (x + 0.02, (a + b) / 2, z0 + head / 2 - 0.02), (0.04, b - a - 0.12, head - 0.1), leaf, collection, cutaway)


def wall_with_openings(name, axis, c0, c1, fixed, z0, z1, thick, openings, wall_mat, frame, glass, leaf, collection, cutaway=False):
    openings = sorted(openings, key=lambda o: o["c"])
    cursor = c0
    for i, o in enumerate(openings):
        a = max(c0 + 0.06, o["c"] - o["w"] / 2)
        b = min(c1 - 0.06, o["c"] + o["w"] / 2)
        if a <= cursor:
            a = cursor + 0.02
        if b <= a:
            continue
        wall_span(f"{name}_s{i}", axis, cursor, a, fixed, z0, z1, thick, wall_mat, collection, cutaway)
        sill = o.get("sill", 0.9)
        head = o.get("head", 2.15)
        if o.get("kind") == "opening":
            wall_span(f"{name}_hd{i}", axis, a, b, fixed, z0 + head, z1, thick, wall_mat, collection, cutaway)
        elif o.get("kind") == "door":
            if sill > 0.04:
                wall_span(f"{name}_th{i}", axis, a, b, fixed, z0, z0 + sill, thick, wall_mat, collection, cutaway)
            wall_span(f"{name}_hd{i}", axis, a, b, fixed, z0 + head, z1, thick, wall_mat, collection, cutaway)
            fill_door(f"{name}_d{i}", axis, a, b, fixed, z0 + sill, head - sill, thick, frame, leaf, collection, cutaway, o.get("interior", False))
        else:
            wall_span(f"{name}_sill{i}", axis, a, b, fixed, z0, z0 + sill, thick, wall_mat, collection, cutaway)
            wall_span(f"{name}_hdr{i}", axis, a, b, fixed, z0 + head, z1, thick, wall_mat, collection, cutaway)
            fill_window(f"{name}_w{i}", axis, a, b, fixed, z0, sill, head, thick, frame, glass, collection, cutaway)
        cursor = b
    wall_span(f"{name}_end", axis, cursor, c1, fixed, z0, z1, thick, wall_mat, collection, cutaway)


def slab_with_hole(name, x0, x1, y0, y1, z, thick, hole, material, collection):
    hx0, hx1, hy0, hy1 = hole
    # four rectangles around the stair opening
    bands = [
        (x0, x1, y0, hy0),
        (x0, x1, hy1, y1),
        (x0, hx0, hy0, hy1),
        (hx1, x1, hy0, hy1),
    ]
    for i, (a, b, c, d) in enumerate(bands):
        if b - a < 0.05 or d - c < 0.05:
            continue
        box(f"{name}_{i}", ((a + b) / 2, (c + d) / 2, z), (b - a, d - c, thick), material, collection)


def make_stairs(prefix, x0, x1, y0, y1, z0, z1, tread_mat, riser_mat, collection, run="+y"):
    rise = z1 - z0
    n = max(12, int(round(rise / 0.175)))
    r = rise / n
    if run == "+y":
        depth = y1 - y0
        t = depth / n
        w = x1 - x0
        for i in range(n):
            y = y0 + (i + 0.5) * t
            box(f"{prefix}_r{i}", ((x0 + x1) / 2, y, z0 + i * r + r / 2), (w, t * 0.92, r), riser_mat, collection)
            box(f"{prefix}_t{i}", ((x0 + x1) / 2, y + t * 0.15, z0 + (i + 1) * r), (w, t * 0.85, 0.04), tread_mat, collection)
        # rail
        box(f"{prefix}_rail", (x1 - 0.04, (y0 + y1) / 2, z0 + rise / 2 + 0.45), (0.05, depth, 0.9), riser_mat, collection)
    else:
        depth = x1 - x0
        t = depth / n
        w = y1 - y0
        for i in range(n):
            x = x0 + (i + 0.5) * t
            box(f"{prefix}_r{i}", (x, (y0 + y1) / 2, z0 + i * r + r / 2), (t * 0.92, w, r), riser_mat, collection)
            box(f"{prefix}_t{i}", (x + t * 0.15, (y0 + y1) / 2, z0 + (i + 1) * r), (t * 0.85, w, 0.04), tread_mat, collection)


def gable_roof(ox, oy, w, d, z, overhang, rise, shingle, fascia, collection):
    oh = overhang
    half = d / 2 + oh
    span = math.hypot(half, rise)
    ang = math.atan2(rise, half)
    cx, cy = ox + w / 2, oy + d / 2
    # south slope
    south = box("roof_south", (cx, cy - half / 2, z + rise / 2), (w + 2 * oh, span, 0.12), shingle, collection)
    south.rotation_euler = (ang, 0, 0)
    north = box("roof_north", (cx, cy + half / 2, z + rise / 2), (w + 2 * oh, span, 0.12), shingle, collection)
    north.rotation_euler = (-ang, 0, 0)
    # gable infill left/right
    gable_h = rise
    box("fascia_eave_s", (cx, oy - oh, z + 0.06), (w + 2 * oh + 0.1, 0.08, 0.14), fascia, collection)
    box("fascia_eave_n", (cx, oy + d + oh, z + 0.06), (w + 2 * oh + 0.1, 0.08, 0.14), fascia, collection)
    return rise


def sofa(name, loc, collection, fabric, wood):
    x, y, z = loc
    box(f"{name}_base", (x, y, z + 0.22), (2.2, 0.9, 0.44), fabric, collection)
    box(f"{name}_back", (x, y + 0.32, z + 0.62), (2.2, 0.28, 0.5), fabric, collection)
    box(f"{name}_al", (x - 0.95, y, z + 0.42), (0.22, 0.9, 0.38), fabric, collection)
    box(f"{name}_ar", (x + 0.95, y, z + 0.42), (0.22, 0.9, 0.38), fabric, collection)


def bed(name, loc, collection, linen, wood, w=1.5, d=2.05):
    x, y, z = loc
    box(f"{name}_frame", (x, y, z + 0.18), (w + 0.08, d + 0.08, 0.28), wood, collection)
    box(f"{name}_matt", (x, y, z + 0.36), (w, d, 0.18), linen, collection)
    box(f"{name}_head", (x, y + d / 2 - 0.04, z + 0.7), (w, 0.08, 0.7), wood, collection)


def table(name, loc, collection, wood, top=(1.5, 0.85, 0.04)):
    x, y, z = loc
    tw, td, th = top
    box(f"{name}_top", (x, y, z + 0.74), top, wood, collection)
    for dx, dy in ((-tw / 2 + 0.08, -td / 2 + 0.08), (tw / 2 - 0.08, -td / 2 + 0.08), (-tw / 2 + 0.08, td / 2 - 0.08), (tw / 2 - 0.08, td / 2 - 0.08)):
        box(f"{name}_leg_{dx}", (x + dx, y + dy, z + 0.36), (0.07, 0.07, 0.72), wood, collection)


def kitchen_run(x0, x1, y, z, collection, cab, counter, backsplash):
    length = x1 - x0
    box("k_base", ((x0 + x1) / 2, y, z + 0.45), (length, 0.6, 0.9), cab, collection)
    box("k_counter", ((x0 + x1) / 2, y, z + 0.92), (length, 0.65, 0.06), counter, collection)
    box("k_splash", ((x0 + x1) / 2, y + 0.28, z + 1.2), (length, 0.04, 0.5), backsplash, collection)
    box("k_upper", ((x0 + x1) / 2, y + 0.12, z + 2.05), (length * 0.7, 0.35, 0.7), cab, collection)


def toilet_vanity(x, y, z, collection, porcelain, wood):
    box("toilet", (x, y, z + 0.22), (0.38, 0.65, 0.42), porcelain, collection)
    box("tank", (x, y + 0.22, z + 0.52), (0.38, 0.18, 0.38), porcelain, collection)
    box("vanity", (x + 0.85, y, z + 0.4), (0.7, 0.48, 0.8), wood, collection)
    box("sink", (x + 0.85, y, z + 0.82), (0.55, 0.38, 0.08), porcelain, collection)


def windows_for_facade(c0, c1, margin=1.1, count=3, kind="window"):
    usable = (c1 - c0) - 2 * margin
    if usable < 1.2:
        return []
    count = max(1, min(count, int(usable / 1.5)))
    openings = []
    for i in range(count):
        c = c0 + margin + (i + 0.5) * (usable / count)
        openings.append({"c": c, "w": 1.2 if kind == "window" else 1.0, "sill": 0.9, "head": 2.2, "kind": kind})
    return openings


def build(spec):
    clear_scene()
    lot_w = float(spec["lot_width"])
    lot_d = float(spec["lot_depth"])
    b = spec["building"]
    bw, bd = float(b["width_m"]), float(b["depth_m"])
    stories = int(b["stories"])
    sh = float(b["story_height_m"])
    front = float(b["setback_front_m"])
    side = float(b["setback_side_m"])
    btype = b.get("building_type", "single_family")
    bedrooms = int(spec.get("bedrooms", 3))
    T, TI = 0.22, 0.12
    slab_t = 0.22
    height = stories * sh

    site = ensure_collection("Site")
    shell = ensure_collection("Shell")
    interior = ensure_collection("Interior")
    furniture = ensure_collection("Furniture")
    landscape = ensure_collection("Landscape")
    systems = ensure_collection("Systems")
    lights = ensure_collection("Lights")

    material_id = b.get("material", "mass_timber")
    ext_rgb = EXTERIOR.get(material_id, EXTERIOR["mass_timber"])
    int_rgb = INTERIOR.get(material_id, INTERIOR["mass_timber"])
    grass = mat("Grass", (0.16, 0.40, 0.13), 0.90)
    soil = mat("Soil", (0.22, 0.14, 0.07), 0.92)
    mulch = mat("Mulch", (0.28, 0.16, 0.08), 0.92)
    sidewalk = mat("Sidewalk", (0.52, 0.50, 0.46), 0.78)
    asphalt = mat("Asphalt", (0.18, 0.18, 0.17), 0.82)
    deck = mat("Deck", (0.42, 0.28, 0.14), 0.55)
    wall = mat("ExtWall", ext_rgb, 0.55)
    plaster = mat("InteriorWall", int_rgb, 0.58)
    floor_wood = mat("FloorWood", (0.48, 0.32, 0.16), 0.38)
    floor_tile = mat("FloorTile", (0.46, 0.30, 0.18), 0.36)
    slab = mat("Slab", (0.46, 0.44, 0.40), 0.62)
    frame = mat("Frame", (0.16, 0.12, 0.08), 0.40, 0.12)
    glass = mat("Glass", (0.20, 0.40, 0.55), 0.08, transmission=0.22, emission=(0.12, 0.24, 0.34), emit=0.03)
    door_leaf = mat("DoorLeaf", (0.28, 0.16, 0.08), 0.42)
    shingle = mat("Shingle", (0.20, 0.14, 0.10), 0.74)
    fascia = mat("Fascia", tuple(max(0.05, c * 0.72) for c in ext_rgb), 0.45)
    roof_mat = mat("RoofDeck", (0.14, 0.32, 0.12) if b["green_roof"] else (0.22, 0.22, 0.24), 0.72)
    solar_mat = mat("Solar", (0.04, 0.08, 0.18), 0.16, 0.70)
    bark = mat("Bark", (0.24, 0.14, 0.07), 0.92)
    leaf = mat("Leaf", CANOPY[0], 0.82)
    shrub = mat("Shrub", (0.18, 0.36, 0.12), 0.86)
    water = mat("Water", (0.16, 0.34, 0.38), 0.10, transmission=0.35)
    fabric = mat("Fabric", (0.22, 0.34, 0.30), 0.72)
    linen = mat("Linen", (0.62, 0.46, 0.28), 0.62)
    wood = mat("Wood", (0.42, 0.26, 0.12), 0.42)
    cab = mat("Cabinet", (0.36, 0.24, 0.12), 0.48)
    counter = mat("Counter", (0.28, 0.30, 0.32), 0.28)
    porcelain = mat("Porcelain", (0.72, 0.70, 0.64), 0.22)
    stair_wood = mat("StairWood", (0.46, 0.30, 0.14), 0.40)

    ox = -lot_w / 2 + side
    oy = -lot_d / 2 + front
    cx, cy = ox + bw / 2, oy + bd / 2

    box("lot", (0, 0, -0.08), (lot_w, lot_d, 0.16), grass, site)
    box("sidewalk", (0, -lot_d / 2 + 0.55, 0.03), (lot_w, 1.1, 0.08), sidewalk, site)
    box("porch", (cx, oy - 1.15, 0.08), (2.6, 1.5, 0.16), deck, site)
    for i in range(3):
        box(f"step_{i}", (cx, oy - 0.35 - i * 0.28, 0.05 + i * 0.05), (1.4, 0.28, 0.1 + i * 0.1), deck, site)
    # front planting beds (park / yard, not bare white lot)
    bed_w = min(3.2, max(1.6, (lot_w - bw) / 2 - 0.4))
    if bed_w > 1.0:
        box("bed_sw", (-lot_w / 2 + bed_w / 2 + 0.4, oy - 0.55, 0.06), (bed_w, 1.6, 0.14), mulch, landscape)
        box("bed_se", (lot_w / 2 - bed_w / 2 - 0.4, oy - 0.55, 0.06), (bed_w, 1.6, 0.14), mulch, landscape)
        for i, px in enumerate((-lot_w / 2 + 1.1, lot_w / 2 - 1.1)):
            box(f"shrub_front_{i}", (px, oy - 0.5, 0.45), (0.7, 0.7, 0.7), shrub, landscape)

    split_x = ox + max(5.4, bw * 0.58)
    split_x = min(split_x, ox + bw - T - 2.6)
    split_y = oy + bd * 0.50
    # Stair in the east hall, running north
    stair_w = 1.05
    stair_run = min(4.3, max(3.5, bd * 0.36))
    sx0 = split_x + TI + 0.15
    sx1 = min(sx0 + stair_w, ox + bw - T - 0.35)
    sy0 = oy + T + 1.55
    sy1 = sy0 + stair_run

    door_x = cx
    # facade windows
    front_opens = [
        {"c": door_x, "w": 1.05, "sill": 0.0, "head": 2.2, "kind": "door"},
        {"c": ox + bw * 0.28, "w": 1.3, "sill": 0.85, "head": 2.25, "kind": "window"},
        {"c": ox + bw * 0.78, "w": 1.3, "sill": 0.85, "head": 2.25, "kind": "window"},
    ]
    back_opens = windows_for_facade(ox, ox + bw, 1.0, 3)
    left_opens = windows_for_facade(oy, oy + bd, 1.3, 3)
    right_opens = windows_for_facade(oy, oy + bd, 1.3, 3)

    for story in range(stories):
        z0 = story * sh
        z1 = z0 + sh - 0.04
        z_floor = z0 + slab_t / 2

        # floor slab (opening for stair except on ground we still cut for visual continuity of well)
        hole = (sx0 - 0.05, sx1 + 0.08, sy0 - 0.05, sy1 + 0.15)
        if story == 0:
            box(f"slab_{story}", (cx, cy, z_floor), (bw + 0.12, bd + 0.12, slab_t), slab, shell)
            # finished floors by room
            box(f"fin_liv_{story}", ((ox + T + split_x) / 2, (oy + T + split_y) / 2, z0 + slab_t + 0.015),
                (split_x - ox - T - 0.02, split_y - oy - T - 0.02, 0.03), floor_wood, interior)
            box(f"fin_kit_{story}", ((ox + T + split_x) / 2, (split_y + oy + bd - T) / 2, z0 + slab_t + 0.015),
                (split_x - ox - T - 0.02, oy + bd - T - split_y - 0.02, 0.03), floor_tile, interior)
            box(
                f"fin_hall_{story}",
                ((split_x + ox + bw - T) / 2, (oy + T + split_y) / 2, z0 + slab_t + 0.015),
                (ox + bw - T - split_x - 0.04, split_y - oy - T - 0.04, 0.03),
                floor_wood,
                interior,
            )
            box(
                f"fin_din_{story}",
                ((split_x + ox + bw - T) / 2, (split_y + oy + bd - T) / 2, z0 + slab_t + 0.015),
                (ox + bw - T - split_x - 0.04, oy + bd - T - split_y - 0.04, 0.03),
                floor_wood,
                interior,
            )
        else:
            slab_with_hole(f"slab_{story}", ox - 0.06, ox + bw + 0.06, oy - 0.06, oy + bd + 0.06, z_floor, slab_t, hole, slab, shell)
            box(f"fin_up_{story}", (cx, cy, z0 + slab_t + 0.015), (bw - 2 * T - 0.05, bd - 2 * T - 0.05, 0.03), floor_wood, interior)

        # exterior walls (front is cutaway-hide)
        wall_with_openings(
            f"front_{story}",
            "x",
            ox,
            ox + bw,
            oy + T / 2,
            z0,
            z1,
            T,
            front_opens if story == 0 else [o for o in front_opens if o["kind"] != "door"]
            + ([{"c": door_x, "w": 1.15, "sill": 0.85, "head": 2.2, "kind": "window"}] if story > 0 else []),
            wall,
            frame,
            glass,
            door_leaf,
            shell,
            cutaway=True,
        )
        wall_with_openings(f"back_{story}", "x", ox, ox + bw, oy + bd - T / 2, z0, z1, T, back_opens, wall, frame, glass, door_leaf, shell)
        wall_with_openings(f"left_{story}", "y", oy, oy + bd, ox + T / 2, z0, z1, T, left_opens, wall, frame, glass, door_leaf, shell)
        wall_with_openings(f"right_{story}", "y", oy, oy + bd, ox + bw - T / 2, z0, z1, T, right_opens, wall, frame, glass, door_leaf, shell)

        # interior partitions
        if story == 0 or btype in {"single_family", "duplex", "townhouse", "community"}:
            # living / stair wall (vertical)
            wall_with_openings(
                f"part_v_{story}",
                "y",
                oy + T,
                oy + bd - T,
                split_x,
                z0 + slab_t,
                z1,
                TI,
                [
                    {"c": (oy + T + split_y) / 2, "w": 0.95, "sill": 0, "head": 2.1, "kind": "door", "interior": True},
                    {"c": (split_y + oy + bd - T) / 2, "w": 0.95, "sill": 0, "head": 2.1, "kind": "door", "interior": True},
                ],
                plaster,
                frame,
                glass,
                door_leaf,
                interior,
            )
            # living / kitchen wall (horizontal) with wide cased opening
            wall_with_openings(
                f"part_h_{story}",
                "x",
                ox + T,
                ox + bw - T,
                split_y,
                z0 + slab_t,
                z1,
                TI,
                [{"c": (ox + T + split_x) / 2, "w": min(2.8, max(1.6, split_x - ox - 1.4)), "sill": 0, "head": 2.2, "kind": "opening"}],
                plaster,
                frame,
                glass,
                door_leaf,
                interior,
            )
            # stair enclosure + bath
            bath_y1 = sy0 - 0.15
            if bath_y1 - (oy + T) > 1.7:
                wall_with_openings(
                    f"bath_{story}",
                    "x",
                    split_x,
                    ox + bw - T,
                    bath_y1,
                    z0 + slab_t,
                    z1,
                    TI,
                    [{"c": split_x + 1.1, "w": 0.85, "sill": 0, "head": 2.1, "kind": "door", "interior": True}],
                    plaster,
                    frame,
                    glass,
                    door_leaf,
                    interior,
                )
                box(f"bath_floor_{story}", ((split_x + ox + bw - T) / 2, (oy + T + bath_y1) / 2, z0 + slab_t + 0.02),
                    (ox + bw - T - split_x - 0.05, bath_y1 - oy - T - 0.05, 0.03), floor_tile, interior)
                toilet_vanity(split_x + 0.7, oy + T + 0.7, z0 + slab_t, furniture, porcelain, wood)

        # stairs (not on the top floor slab going nowhere — they go up to next floor)
        if story < stories - 1:
            make_stairs(f"stair_{story}", sx0 + 0.02, sx1 - 0.02, sy0, sy1, z0 + slab_t, z0 + sh, stair_wood, plaster, interior)
        elif stories == 1:
            pass

        # lights
        add_point_light(f"L_liv_{story}", ((ox + split_x) / 2, (oy + split_y) / 2, z1 - 0.18), 85, lights, 1.2)
        add_point_light(f"L_kit_{story}", ((ox + split_x) / 2, (split_y + oy + bd) / 2, z1 - 0.18), 75, lights, 1.0)
        add_point_light(f"L_east_{story}", ((split_x + ox + bw) / 2, cy, z1 - 0.18), 60, lights, 0.9)

        # furniture
        if story == 0:
            liv_x = (ox + T + split_x) / 2
            liv_y = (oy + T + split_y) / 2 - 0.2
            sofa("sofa", (liv_x, liv_y - 0.4, z0 + slab_t), furniture, fabric, wood)
            table("coffee", (liv_x, liv_y + 0.55, z0 + slab_t), furniture, wood, (1.1, 0.55, 0.04))
            kitchen_run(ox + T + 0.35, split_x - 0.35, oy + bd - T - 0.38, z0 + slab_t, furniture, cab, counter, mat("Splash", (0.55, 0.62, 0.58), 0.3))
            table("dining", ((split_x + ox + bw - T) / 2, (split_y + oy + bd - T) / 2, z0 + slab_t), furniture, wood, (1.4, 0.85, 0.04))
            box("entry_bench", (split_x + 0.7, oy + T + 0.55, z0 + slab_t + 0.22), (1.1, 0.4, 0.44), fabric, furniture)
        else:
            # bedrooms
            bed("bed_sw", ((ox + T + split_x) / 2, (oy + T + split_y) / 2, z0 + slab_t), furniture, linen, wood)
            table("desk", ((ox + T + split_x) / 2 + 1.2, split_y - 0.7, z0 + slab_t), furniture, wood, (1.1, 0.55, 0.04))
            if bedrooms >= 2:
                bed("bed_nw", ((ox + T + split_x) / 2, (split_y + oy + bd - T) / 2, z0 + slab_t), furniture, linen, wood, w=1.35, d=1.95)
            if bedrooms >= 3:
                bed("bed_ne", ((split_x + ox + bw - T) / 2, (split_y + oy + bd - T) / 2, z0 + slab_t), furniture, linen, wood, w=1.2, d=1.9)

    # roof
    roof_z = height
    if b["roof_type"] == "pitched":
        gable_roof(ox, oy, bw, bd, roof_z, 0.4, min(2.4, bw * 0.22), shingle, fascia, shell)
    else:
        box("roof_deck", (cx, cy, roof_z + 0.08), (bw + 0.2, bd + 0.2, 0.16), roof_mat, shell)
        box("parapet_n", (cx, oy + bd + 0.05, roof_z + 0.32), (bw + 0.25, 0.12, 0.45), wall, shell)
        box("parapet_s", (cx, oy - 0.05, roof_z + 0.32), (bw + 0.25, 0.12, 0.45), wall, shell)
        box("parapet_e", (ox + bw + 0.05, cy, roof_z + 0.32), (0.12, bd, 0.45), wall, shell)
        box("parapet_w", (ox - 0.05, cy, roof_z + 0.32), (0.12, bd, 0.45), wall, shell)
        if b["green_roof"]:
            box("green_soil", (cx, cy, roof_z + 0.2), (bw - 0.6, bd - 0.6, 0.14), soil, systems)
            rows, cols = 3, 4
            for r in range(rows):
                for c in range(cols):
                    px = ox + 1.2 + c * ((bw - 2.4) / max(cols - 1, 1))
                    py = oy + 1.2 + r * ((bd - 2.4) / max(rows - 1, 1))
                    box(f"plant_{r}_{c}", (px, py, roof_z + 0.42), (0.5, 0.5, 0.32), leaf, systems)

    if b["solar_panels"]:
        for r in range(2):
            for c in range(3):
                box(
                    f"pv_{r}_{c}",
                    (cx + 0.4 + c * 1.25, cy + 0.2 + r * 1.0, roof_z + 0.38),
                    (1.15, 0.7, 0.05),
                    solar_mat,
                    systems,
                )

    if b["rain_garden"]:
        gx, gy = ox + bw + 2.2, oy + bd - 2.5
        box("rain_garden", (gx, gy, 0.04), (3.2, 2.2, 0.18), soil, landscape)
        box("cistern_water", (gx, gy, 0.1), (2.0, 1.2, 0.1), water, landscape)
        box("cistern", (gx + 1.4, gy + 1.1, 0.7), (0.85, 0.85, 1.25), mat("Tank", (0.32, 0.46, 0.38), 0.4), systems)

    if int(b["parking_spaces"]) > 0:
        stall_w = min(2.6 * min(int(b["parking_spaces"]), 3), lot_w * 0.4)
        box("parking", (lot_w / 2 - stall_w / 2 - 0.5, -lot_d / 2 + 3.4, 0.03), (stall_w, 5.4, 0.08), asphalt, site)
        if b["ev_charging"]:
            box("ev_charger", (lot_w / 2 - 1.1, -lot_d / 2 + 5.8, 0.7), (0.22, 0.22, 1.3), frame, systems)

    n = int(b["tree_count"])
    for i in range(n):
        t = (i + 0.35) / max(n, 1)
        if i % 2 == 0:
            x, y = -lot_w / 2 + 1.2, -lot_d / 2 + 2.8 + t * (lot_d - 5)
        else:
            x, y = lot_w / 2 - 1.4, lot_d / 2 - 2.2 - t * (lot_d * 0.4)
        h = 3.4 + (i % 5) * 0.2
        canopy = mat(f"Canopy_{i}", CANOPY[i % len(CANOPY)], 0.84)
        box(f"trunk_{i}", (x, y, h * 0.28), (0.28, 0.28, h * 0.55), bark, landscape)
        box(f"canopy_{i}", (x, y, h * 0.78), (1.5, 1.5, h * 0.5), canopy, landscape)

    # cameras
    liv_target = ((ox + split_x) / 2 + 0.2, split_y - 0.35, 1.2)
    interior_cam = (ox + T + 1.85, oy + T + 2.15, 1.58)
    dist = max(lot_w, lot_d, height) * 0.95 + 6
    ext = add_camera("CameraExterior", (cx + dist * 0.55, cy - dist * 0.9, height * 0.45 + 5.5), (cx, cy, height * 0.35), 32)
    add_camera("CameraInterior", interior_cam, liv_target, 28)
    add_camera("CameraCutaway", (cx, oy - 8.5, 2.4), (cx, cy + 0.8, 1.5), 30)
    bpy.context.scene.camera = ext

    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = 2.2
    sun = bpy.data.objects.new("Sun", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(48), math.radians(8), math.radians(-35))

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.38, 0.55, 0.72, 1)
        bg.inputs[1].default_value = 0.62

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0

    def b2t(p):
        return [p[0], p[2], -p[1]]

    return {
        "exterior": {"position": b2t(list(ext.location)), "target": b2t([cx, cy, height * 0.35])},
        "interior": {"position": b2t(list(interior_cam)), "target": b2t(list(liv_target))},
        "cutaway": {"position": b2t([cx, oy - 8.5, 2.4]), "target": b2t([cx, cy + 0.8, 1.5])},
    }


def setup_render(scene):
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            scene.render.engine = "CYCLES"
            scene.cycles.samples = 24


def hide_cutaway(hide: bool):
    for obj in bpy.data.objects:
        if obj.name.startswith("CUTAWAY_"):
            obj.hide_render = hide
            obj.hide_viewport = hide


def export_all(out_dir: Path, views: dict):
    (out_dir / "views.json").write_text(json.dumps(views, indent=2), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / "model.blend"))

    bpy.ops.export_scene.gltf(
        filepath=str(out_dir / "model.glb"),
        export_format="GLB",
        export_apply=True,
        export_cameras=True,
        export_lights=False,
    )
    try:
        bpy.ops.wm.stl_export(filepath=str(out_dir / "model.stl"), export_selected_objects=False)
    except Exception:
        try:
            bpy.ops.export_mesh.stl(filepath=str(out_dir / "model.stl"))
        except Exception as exc:
            print("STL export failed:", exc)

    scene = bpy.context.scene
    setup_render(scene)
    cams = {obj.name: obj for obj in bpy.data.objects if obj.type == "CAMERA"}

    def render_cam(cam_name, filename, cutaway=False):
        cam = cams.get(cam_name)
        if not cam:
            return
        hide_cutaway(cutaway)
        scene.camera = cam
        scene.render.filepath = str(out_dir / filename)
        try:
            bpy.ops.render.render(write_still=True)
        except Exception as exc:
            print("render skipped", filename, exc)
        hide_cutaway(False)

    render_cam("CameraExterior", "preview.png", False)
    render_cam("CameraInterior", "interior.png", False)
    render_cam("CameraCutaway", "cutaway.png", True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / "model.blend"))


def main():
    args = parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    views = build(spec)
    export_all(out, views)
    print("ECO_INFRA_STUDIO_OK")


if __name__ == "__main__":
    main()
