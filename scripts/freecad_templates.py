"""
CAD Script Templates for common 3D objects.

These templates serve as reference for Kiro (LLM) when generating CadQuery scripts.
Each template is a working CadQuery script that can be customized with parameters.

Usage by Kiro:
1. Identify which template best matches the user's request
2. Modify parameters (dimensions, features) to match requirements
3. Combine templates for complex objects
4. Pass the generated script to text_to_cad.execute_cadquery_script()
"""


# ============================================================
# Basic Shapes
# ============================================================

BOX = """
import cadquery as cq

# Simple box with optional fillet edges
width = {width}   # mm
depth = {depth}   # mm
height = {height}  # mm
fillet = {fillet}  # mm (0 for sharp edges)

result = cq.Workplane("XY").box(width, depth, height)

if fillet > 0:
    result = result.edges("|Z").fillet(fillet)
"""

CYLINDER = """
import cadquery as cq

# Cylinder with optional center hole
radius = {radius}       # mm
height = {height}       # mm
hole_radius = {hole_radius}  # mm (0 for solid)

result = cq.Workplane("XY").circle(radius).extrude(height)

if hole_radius > 0:
    result = result.faces(">Z").workplane().hole(hole_radius * 2)
"""

SPHERE = """
import cadquery as cq

# Sphere
radius = {radius}  # mm

result = cq.Workplane("XY").sphere(radius)
"""


# ============================================================
# Enclosures & Cases
# ============================================================

ENCLOSURE_BOX = """
import cadquery as cq

# Rectangular enclosure (open top box with walls)
inner_width = {inner_width}    # mm
inner_depth = {inner_depth}    # mm
inner_height = {inner_height}  # mm
wall_thickness = {wall_thickness}  # mm
fillet = {fillet}  # mm

# Outer dimensions
ow = inner_width + 2 * wall_thickness
od = inner_depth + 2 * wall_thickness
oh = inner_height + wall_thickness  # bottom wall

# Create outer shell
result = cq.Workplane("XY").box(ow, od, oh)

# Cut inner cavity
result = (
    result
    .faces(">Z").workplane()
    .rect(inner_width, inner_depth)
    .cutBlind(-inner_height)
)

# Optional fillet on outer edges
if fillet > 0:
    result = result.edges("|Z").fillet(fillet)
"""

ENCLOSURE_WITH_LID = """
import cadquery as cq

# Box with snap-fit lid
inner_width = {inner_width}    # mm
inner_depth = {inner_depth}    # mm
inner_height = {inner_height}  # mm
wall = {wall_thickness}        # mm
lip_height = 2.0               # mm (lid overlap)

# === Bottom part ===
ow = inner_width + 2 * wall
od = inner_depth + 2 * wall

bottom = (
    cq.Workplane("XY")
    .box(ow, od, inner_height + wall)
    .faces(">Z").workplane()
    .rect(inner_width, inner_depth)
    .cutBlind(-inner_height)
)

# Add lip for lid
bottom = (
    bottom
    .faces(">Z").workplane()
    .rect(inner_width - 0.4, inner_depth - 0.4)
    .extrude(lip_height)
)

result = bottom
"""

RASPBERRY_PI_CASE = """
import cadquery as cq

# Raspberry Pi 4 case (inner: 85 x 56 x 20 mm)
inner_w = 85.0
inner_d = 56.0
inner_h = 20.0
wall = 2.0

ow = inner_w + 2 * wall
od = inner_d + 2 * wall
oh = inner_h + wall

# Main body
result = (
    cq.Workplane("XY")
    .box(ow, od, oh)
    .faces(">Z").workplane()
    .rect(inner_w, inner_d)
    .cutBlind(-inner_h)
    .edges("|Z").fillet(2.0)
)

# USB-C port cutout (centered on short side)
result = (
    result
    .faces("<Y").workplane(centerOption="CenterOfMass")
    .center(0, -inner_h/2 + 5)
    .rect(9, 4).cutBlind(-wall - 1)
)

# HDMI port cutouts (2x micro HDMI)
result = (
    result
    .faces("<Y").workplane(centerOption="CenterOfMass")
    .center(-15, -inner_h/2 + 5)
    .rect(7, 4).cutBlind(-wall - 1)
)
result = (
    result
    .faces("<Y").workplane(centerOption="CenterOfMass")
    .center(-27, -inner_h/2 + 5)
    .rect(7, 4).cutBlind(-wall - 1)
)

# USB-A ports (side)
result = (
    result
    .faces(">X").workplane(centerOption="CenterOfMass")
    .center(-10, -inner_h/2 + 8)
    .rect(15, 16).cutBlind(-wall - 1)
)

# SD card slot (bottom)
result = (
    result
    .faces(">Y").workplane(centerOption="CenterOfMass")
    .center(15, -inner_h/2 + 2)
    .rect(12, 3).cutBlind(-wall - 1)
)

# Ventilation holes (top)
result = (
    result
    .faces(">Z").workplane()
    .rarray(4, 4, 8, 6)
    .hole(1.5, wall)
)

# Mounting posts
post_h = inner_h - 3
for x, y in [(3.5, 3.5), (3.5 + 58, 3.5), (3.5, 3.5 + 49), (3.5 + 58, 3.5 + 49)]:
    result = (
        result
        .faces("<Z").workplane(offset=-wall)
        .center(x - inner_w/2, y - inner_d/2)
        .circle(2.5).extrude(post_h)
        .faces(">Z").workplane()
        .center(x - inner_w/2, y - inner_d/2)
        .hole(2.0, post_h)
    )
"""


# ============================================================
# Mechanical Parts
# ============================================================

BRACKET_L = """
import cadquery as cq

# L-shaped mounting bracket
width = {width}          # mm
height = {height}        # mm
depth = {depth}          # mm
thickness = {thickness}  # mm
hole_dia = {hole_diameter}  # mm
fillet = {fillet}        # mm

# Vertical plate
result = (
    cq.Workplane("XY")
    .box(width, thickness, height)
    .translate((0, depth/2 - thickness/2, height/2))
)

# Horizontal plate
base = (
    cq.Workplane("XY")
    .box(width, depth, thickness)
    .translate((0, 0, thickness/2))
)

result = result.union(base)

# Fillet the inner corner
if fillet > 0:
    result = result.edges("|X").fillet(fillet)

# Mounting holes in base
result = (
    result
    .faces("<Z").workplane()
    .rarray(width * 0.6, depth * 0.5, 2, 1)
    .hole(hole_dia)
)

# Mounting holes in vertical plate
result = (
    result
    .faces(">Y").workplane()
    .rarray(width * 0.6, height * 0.5, 2, 1)
    .hole(hole_dia)
)
"""

GEAR_SPUR = """
import cadquery as cq
import math

# Spur gear (simplified profile)
num_teeth = {num_teeth}
module = {module}         # mm
thickness = {thickness}   # mm
bore_dia = {bore_diameter}  # mm (center hole)
pressure_angle = 20       # degrees

# Calculate gear dimensions
pitch_dia = module * num_teeth
outer_dia = pitch_dia + 2 * module
root_dia = pitch_dia - 2.5 * module

# Create base cylinder
result = cq.Workplane("XY").circle(outer_dia / 2).extrude(thickness)

# Cut simplified tooth gaps (approximation)
tooth_angle = 360.0 / num_teeth
gap_width = math.pi * module * 0.5

for i in range(num_teeth):
    angle = math.radians(i * tooth_angle)
    x = (pitch_dia / 2) * math.cos(angle)
    y = (pitch_dia / 2) * math.sin(angle)

    result = (
        result
        .faces(">Z").workplane()
        .center(x, y)
        .rect(gap_width * 0.4, module * 2, centered=True)
        .rotateAboutCenter((0, 0, 1), math.degrees(angle))
        .cutBlind(-thickness)
    )

# Center bore
if bore_dia > 0:
    result = (
        cq.Workplane("XY")
        .circle(outer_dia / 2).extrude(thickness)
        .faces(">Z").workplane()
        .hole(bore_dia)
    )
"""

PHONE_STAND = """
import cadquery as cq

# Adjustable phone/tablet stand
base_width = {base_width}    # mm
base_depth = {base_depth}    # mm
base_height = {base_height}  # mm
angle = {angle}              # degrees from vertical
slot_width = {slot_width}    # mm (for phone thickness)
wall = 3.0

# Base plate
result = (
    cq.Workplane("XY")
    .box(base_width, base_depth, base_height)
    .edges("|Z").fillet(3)
)

# Back support (angled)
import math
support_height = 80
support_depth = support_height * math.tan(math.radians(angle))

back = (
    cq.Workplane("XZ")
    .center(0, base_height)
    .lineTo(0, support_height)
    .lineTo(support_depth, 0)
    .close()
    .extrude(wall)
    .translate((0, -wall/2, 0))
)

result = result.union(back)

# Front lip to hold phone
lip = (
    cq.Workplane("XY")
    .box(base_width, slot_width + wall*2, 15)
    .translate((0, -base_depth/2 + (slot_width + wall*2)/2, base_height/2 + 7.5))
)

# Cut slot in lip
lip = (
    lip
    .faces(">Z").workplane()
    .rect(base_width - wall*4, slot_width)
    .cutBlind(-12)
)

result = result.union(lip)
"""

THREADED_KNOB = """
import cadquery as cq

# Knurled knob with threaded insert
knob_dia = {knob_diameter}   # mm
knob_height = {knob_height}  # mm
thread_dia = {thread_diameter}  # mm (e.g., M5 = 5)
num_knurls = {num_knurls}    # number of grip ridges

import math

# Main body
result = cq.Workplane("XY").circle(knob_dia / 2).extrude(knob_height)

# Top dome
result = (
    result
    .faces(">Z").workplane()
    .circle(knob_dia / 2 - 1)
    .extrude(3, taper=30)
)

# Knurl cuts (simplified as flats)
for i in range(num_knurls):
    angle = i * (360.0 / num_knurls)
    x = (knob_dia / 2 + 1) * math.cos(math.radians(angle))
    y = (knob_dia / 2 + 1) * math.sin(math.radians(angle))
    result = (
        result
        .faces(">Z").workplane(offset=-knob_height - 3)
        .center(x, y)
        .rect(2, 3)
        .cutBlind(knob_height + 3)
    )

# Thread hole
result = (
    result
    .faces("<Z").workplane()
    .hole(thread_dia, knob_height * 0.8)
)
"""


# ============================================================
# Template Registry
# ============================================================

TEMPLATES = {
    "box": {
        "script": BOX,
        "description": "Simple box with optional fillets",
        "params": {"width": 50, "depth": 30, "height": 20, "fillet": 2},
        "keywords": ["box", "cube", "block", "rectangular"],
    },
    "cylinder": {
        "script": CYLINDER,
        "description": "Cylinder with optional center hole",
        "params": {"radius": 20, "height": 40, "hole_radius": 0},
        "keywords": ["cylinder", "tube", "pipe", "round", "circular"],
    },
    "sphere": {
        "script": SPHERE,
        "description": "Sphere",
        "params": {"radius": 25},
        "keywords": ["sphere", "ball", "globe"],
    },
    "enclosure": {
        "script": ENCLOSURE_BOX,
        "description": "Open-top rectangular enclosure",
        "params": {"inner_width": 60, "inner_depth": 40, "inner_height": 25,
                   "wall_thickness": 2, "fillet": 2},
        "keywords": ["enclosure", "case", "box", "container", "housing"],
    },
    "enclosure_lid": {
        "script": ENCLOSURE_WITH_LID,
        "description": "Enclosure with snap-fit lid",
        "params": {"inner_width": 60, "inner_depth": 40, "inner_height": 25,
                   "wall_thickness": 2},
        "keywords": ["lid", "cover", "snap", "enclosed"],
    },
    "raspberry_pi_case": {
        "script": RASPBERRY_PI_CASE,
        "description": "Raspberry Pi 4 case with ports and ventilation",
        "params": {},
        "keywords": ["raspberry", "pi", "rpi", "sbc"],
    },
    "bracket_l": {
        "script": BRACKET_L,
        "description": "L-shaped mounting bracket with holes",
        "params": {"width": 40, "height": 50, "depth": 30,
                   "thickness": 3, "hole_diameter": 5, "fillet": 5},
        "keywords": ["bracket", "mount", "l-shape", "angle"],
    },
    "gear": {
        "script": GEAR_SPUR,
        "description": "Simplified spur gear",
        "params": {"num_teeth": 20, "module": 2, "thickness": 8,
                   "bore_diameter": 6},
        "keywords": ["gear", "cog", "spur", "teeth"],
    },
    "phone_stand": {
        "script": PHONE_STAND,
        "description": "Phone/tablet stand with angled support",
        "params": {"base_width": 80, "base_depth": 60, "base_height": 5,
                   "angle": 15, "slot_width": 12},
        "keywords": ["stand", "phone", "tablet", "holder", "dock"],
    },
    "knob": {
        "script": THREADED_KNOB,
        "description": "Knurled knob with threaded insert hole",
        "params": {"knob_diameter": 30, "knob_height": 15,
                   "thread_diameter": 5, "num_knurls": 16},
        "keywords": ["knob", "dial", "handle", "grip"],
    },
}


def get_template(name: str) -> dict | None:
    """Get a template by name."""
    return TEMPLATES.get(name)


def find_template(query: str) -> list:
    """Find templates matching a query string."""
    query_lower = query.lower()
    matches = []

    for name, template in TEMPLATES.items():
        score = 0
        # Check keywords
        for kw in template["keywords"]:
            if kw in query_lower:
                score += 10
        # Check description
        if any(word in template["description"].lower() for word in query_lower.split()):
            score += 5
        # Check name
        if name in query_lower:
            score += 15

        if score > 0:
            matches.append((name, template, score))

    matches.sort(key=lambda x: x[2], reverse=True)
    return matches


def render_template(name: str, **params) -> str:
    """
    Render a template with custom parameters.

    Args:
        name: Template name.
        **params: Override default parameters.

    Returns:
        Rendered Python script string.
    """
    template = TEMPLATES.get(name)
    if not template:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATES.keys())}")

    # Merge defaults with provided params
    final_params = {**template["params"], **params}

    return template["script"].format(**final_params)


def list_templates() -> str:
    """List all available templates with descriptions."""
    lines = ["\nAvailable CAD Templates:", "=" * 50]
    for name, tmpl in TEMPLATES.items():
        lines.append(f"  {name:20s} - {tmpl['description']}")
        if tmpl["params"]:
            params_str = ", ".join(f"{k}={v}" for k, v in tmpl["params"].items())
            lines.append(f"  {'':20s}   Params: {params_str}")
    lines.append("=" * 50)
    return "\n".join(lines)


if __name__ == "__main__":
    print(list_templates())
