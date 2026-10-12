"""Mutaciones textuales sobre un .py recién generado, para sembrar defectos en las pruebas.

Se aplican sobre la salida fresca del generador (no sobre copias commiteadas), así no se
desincronizan cuando cambia el formato.
"""

import re


def _edge_lines(src):
    return [i for i, l in enumerate(src.splitlines()) if re.match(r"\s+\w+ (>>|-) link\(", l)]


def _replace_line(src, idx, fn):
    lines = src.splitlines()
    lines[idx] = fn(lines[idx])
    return "\n".join(lines) + "\n"


def drop_edge(src, n=0):
    lines = src.splitlines()
    del lines[_edge_lines(src)[n]]
    return "\n".join(lines) + "\n"


def reverse_edge(src, n=0):
    def swap(line):
        m = re.match(r"(\s+)(\w+) (>>|-) (link\(.*\)) (>>|-) (\w+)$", line)
        return f"{m[1]}{m[6]} {m[3]} {m[4]} {m[5]} {m[2]}"
    return _replace_line(src, _edge_lines(src)[n], swap)


def change_edge_label(src, n=0, label="otro"):
    return _replace_line(src, _edge_lines(src)[n], lambda l: re.sub(r'label="[^"]*"', f'label="{label}"', l))


def non_canonical_edge(src, n=0):
    def plain(line):
        m = re.match(r"(\s+)(\w+) (>>|-) link\(.*\) (>>|-) (\w+)$", line)
        return f"{m[1]}{m[2]} >> {m[5]}"
    return _replace_line(src, _edge_lines(src)[n], plain)


def extra_node(src):
    return src.replace("    # --- edges ---", '    fantasma = EC2("Fantasma", nodeid="fantasma")\n\n    # --- edges ---', 1)


def remove_node(src, var="cache"):
    return "\n".join(l for l in src.splitlines() if not re.match(rf"\s+{var} = ", l)) + "\n"


def move_node_to_root(src, var="web"):
    lines = src.splitlines()
    i = next(k for k, l in enumerate(lines) if re.match(rf"\s+{var} = ", l))
    line = lines.pop(i).strip()
    lines.insert(next(k for k, l in enumerate(lines) if l.startswith("    with Cluster(")), "    " + line)
    return "\n".join(lines) + "\n"


def inject_edge_fontsize(src):
    return src.replace('link(label="HTTPS"', 'link(fontsize="20", label="HTTPS"', 1)


def inject_hex_outside_style(src):
    return src.replace("\n\nwith Diagram(", '\n\nFONDO = "#ff0000"\n\nwith Diagram(', 1)


def inject_edge_color(src):
    return src.replace('link(label="HTTPS"', 'link(color="#ff0000", label="HTTPS"', 1)


def inject_font_literal(src):
    return src.replace('link(label="HTTPS"', 'link(fontname="Helvetica", label="HTTPS"', 1)


def blocked_font(src):
    return src.replace('FONT_FAMILY       = "Helvetica"', 'FONT_FAMILY       = "Comic Sans MS"', 1)


def break_import(src):
    return src.replace("RDS", "RDSX", 1)


def remove_show_false(src):
    return src.replace("    show=False,\n", "", 1)


def remove_nodeid(src):
    return src.replace(', nodeid="web"', "", 1)


def cluster_without_zone(src):
    return src.replace('with Cluster("VPC", graph_attr=zone(0)):', 'with Cluster("VPC"):', 1)


def ortho_splines(src):
    return src.replace('SPLINES           = "spline"', 'SPLINES           = "ortho"', 1)


def change_zone(src):
    return src.replace('graph_attr=zone(0)', 'graph_attr=zone(3)', 1)


def ortho_label_kwarg(src):
    """xlabel= -> label= en las aristas: reintroduce el defecto que el generador evita con ortho."""
    return src.replace("xlabel=", "label=")


def edit_style_only(src):
    return src.replace('FONT_SIZE_NODE    = "12"', 'FONT_SIZE_NODE    = "14"', 1)
