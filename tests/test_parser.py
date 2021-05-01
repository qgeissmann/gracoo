import os
from typing import Dict
import re
import networkx as nx
import textwrap
from networkx.drawing.nx_agraph import to_agraph


def parse_ingredient(ingredient: str) -> Dict:
    m = re.match(r'\s*(?P<ingr>\w+)\s*(\[(?P<amount>.*)\])?', ingredient)
    amount = m["amount"]
    if amount:
        amount = amount.strip()
    return {"name":m["ingr"], "amount": amount}

def parse_process(process: str) -> Dict:
    m = re.match(r'\s*(?P<proc>\w+)\s*(\[(?P<args>.*)\])?', process)
    if m["args"]:
        args = [a.strip() for a in m["args"].split(',')]
    else:
        args = []
    return {"name":m["proc"], "arguments": args}

def parse_line(line:str) -> Dict:
    l = line
    m = re.match(r'\s*(?P<inputs>[\w,\s\.\[\]]+)\s*(\|\s*(?P<processes>[\w\s\|\[\]\.\,]+)\s*(>\s*(?P<outputs>[\w,\.\s]+))?)?\s*(#\s*(?P<comment>.*))?', l)


    assert m, f"Error parsing {l}"

    if m['comment']:
        comment = m['comment'].rstrip().strip()
    else:
        comment = None

    inputs = [parse_ingredient(i) for i in m['inputs'].split(',')]
    if m["processes"] is None:
        return {"inputs": inputs,
                "processes": None,
                "outputs": None,
                "comment": comment
                }

    if m['outputs'] is None:
        outputs = inputs
    else:
        outputs = [parse_ingredient(i) for i in m['outputs'].split(',')]

    processes = [parse_process(i) for i in m['processes'].split('|')]

    return {"inputs": inputs,
            "processes": processes,
            "outputs": outputs,
            "comment": comment
            }


carrot = {"name":"carrot","amount":None}

# expected = {"carrot | peel": {"inputs": [carrot],
#                               "processes": [{"name": "peel", "arguments": []}],
#                               "outputs": [carrot]},
#             "carrot | peel| bake[10 min, 200 C]": {"inputs": [carrot],
#                               "processes": [{"name": "peel", "arguments": []},
#                                             {"name": "bake", "arguments": ["10 min", "200 C"]}],
#                               "outputs": [carrot]},
#             "carrot, salt [5g ] | bake[10 min, 200 C] >mix":
#                         {"inputs": [carrot, {"name":"salt","amount":"5g"}],
#                                           "processes": [{"name": "bake", "arguments": ["10 min", "200 C"]}],
#                                           "outputs": [{"name":"mix", "amount":None}]}
#
#             }
#
# for s, e in expected.items():
#     p = parse_line(s)
#     if p != e:
#         print(e)
#         print(p)
#         raise AssertionError(f"Unexpected return parsing {s}")
#



def parse_flow(flow):
    # name-N is a unique ID for a node, the same ingredient can be in multiple nodes for synonymous processes
    # ingredient_nodes = {f"{i['name']}_0_0": i for i in ingredients}
    ingredient_nodes = {}
    current_ingredients = {}
    process_nodes = {}
    edges = []
    comments = []

    for e, f in enumerate(flow):
        j = e + 1
        f = f.rstrip()
        line = parse_line(f)
        if line["processes"] is None:
            for i in line["inputs"]:
                assert i['name'] not in current_ingredients.keys(), f"Duplicated ingredient `{i['name']}'"
                ingredient_nodes[f"{i['name']}_0_0"] = i
                current_ingredients[i['name']] = f"{i['name']}_0_0"

            continue
        for i in line["inputs"]:
            assert i["name"] in current_ingredients, f"Flow parsing error. Line {e}: `{f}'. Input `{i['name']}' not in previous outputs / ingredients ({current_ingredients.keys()})"

        # special case if names of inputs are the same as names of outputs we apply process to each pair?
        current_comment = {"value": line["comment"], "start_node": None, "end_node": None}
        for k, p in enumerate(line["processes"]):
            process_key = f"{p['name']}_{j}_{k}"
            if current_comment["start_node"] is None:
                current_comment["start_node"] = process_key
            current_comment["end_node"] = process_key
            process_nodes[process_key] = p
            if k == 0:
                for i in line["inputs"]:
                    node_key = current_ingredients[i["name"]]
                    edges.append((node_key, process_key, i["amount"]))

            else:
                edges.append((output_key, process_key, None))

            if k < len(line["processes"]) -1:
                outputs = [{"name": None, "amount":None}]
            else:
                outputs = line["outputs"]

            for o in outputs:
                if o["name"] is None:
                    output_key = f"anonymous_{j}_{k}"
                else:
                    output_key = f"{o['name']}_{j}_{k}"
                o["amount"] = None
                current_ingredients[o["name"]] = output_key
                ingredient_nodes[output_key] = o
                edges.append((process_key, output_key, None))
        if current_comment["value"] is not None:
            comments.append(current_comment)
    return ingredient_nodes, process_nodes, edges, comments


def make_nx_graph(ing, proc, edg):
    G = nx.DiGraph()
    for k, v in ing.items():
        if v["amount"]:
            lab = f'{v["name"]}'
        else:
            lab = v["name"]
        G.add_node(k, label=lab, type="ingredient", amount=f'{v["amount"]}')

    for k, v in proc.items():
        if v["arguments"]:
            lab = v["name"] + "\n" + "\n".join(v["arguments"])
        else:
            lab = v["name"]

        G.add_node(k, label=lab, type="process")

    for a, b, l in edg:
        if not l:
            l = ""
        G.add_edge(a, b, label=l)

    for id, attrs in G.nodes(data=True):
        if attrs["type"] == "ingredient":
            preds = [p for p in G.predecessors(id)]
            if len(preds) == 0:
                G.nodes[id]["type"] = "primary_ingredient"

    # simplify graph here
    to_remove = []
    new_edges = []
    for id, attrs in G.nodes(data=True):
        if attrs["type"] == "ingredient" and attrs["label"] is None:
            preds = [p for p in G.predecessors(id)]
            succs = [p for p in G.successors(id)]
            assert len(preds) == 1
            assert len(succs) == 1
            to_remove.append(id)
            new_edges.append((preds[0], succs[0]))

    for r in to_remove:
        G.remove_node(r)
    for e in new_edges:
        G.add_edge(*e, test=1)

    removed = True
    while removed:
        removed = False
        for id, attrs in G.nodes(data=True):
            if attrs["type"] == "ingredient":
                scope = id
                while True:

                    preds = [p for p in G.predecessors(scope)]
                    succs = [p for p in G.successors(scope)]
                    if len(preds) != 1 or len(succs) != 1:
                        break
                    pred = G.nodes[preds[0]]

                    if pred['type'] == "process":
                        scope = preds[0]
                        continue

                    if pred["label"] == attrs["label"]:
                        G.add_edge([p for p in G.predecessors(id)][0],
                                   [p for p in G.successors(id)][0])
                        G.remove_node(id)
                        removed = True
                        break
                    else:
                        break
            if removed:
                break

    return G

def render_graph(G, comments):
    A = to_agraph(G)
    A.graph_attr["nodesep"] = .05
    A.graph_attr["ranksep"] = .1
    A.graph_attr["margin"] = 0
    A.graph_attr["autosize"] = False
    A.graph_attr["ratio"] = "auto" # fail
    A.graph_attr["size"] = "10,10"


    type_attr_map = {"process": {"shape":"plaintext",
                                 # "fillcolor":"#88f877",
                                 #  "style":"filled"
                                 },
                     "ingredient": {"shape":"octagon",
                                    "fillcolor":"#7788f8",
                                    "style":"filled"},
                     "primary_ingredient": {"shape": "rectangle",
                                    "fillcolor": "#99eef8",
                                    "style": "filled"}
                     }
    for n in A.iternodes():
        for k,v in type_attr_map[n.attr["type"]].items():
            n.attr[k] = v
        n.attr["margin"] = "0.001"
        n.attr["width"] = "0.01"
        if n.attr["type"] == "primary_ingredient" and n.attr["amount"] != "None":
            n.attr["label"] = n.attr["label"] + "\n" + n.attr["amount"]
        if n.attr["type"] == "process":
            lines = n.attr["label"].split("\n")
            formated_lines = []
            for l in lines:
                if formated_lines:
                    port = "text"
                else:
                    port = "title"
                formated_lines.append(f"<TR><TD bgcolor='#88f877' PORT='{port}'>{l}<br /></TD></TR>'")
            formated_lines = "\n".join(formated_lines)
            n.attr["label"] = f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0"> {formated_lines}</TABLE>>'

    for i,c in enumerate(comments):
        for n in A.nodes_iter():
            if str(n) == c["start_node"]:
                start_node = str(n)
            if str(n) == c["end_node"]:
                end_node = str(n)
                # print(end_node)
        comment_node_label = f'{c["value"]}_{i}'
        comment = "\n".join(textwrap.wrap(c["value"], 30))

        # A.add_node(comment_node_label, label="<<I> " + comment + "</I>>", shape="plaintext", color="#f80000")
        A.add_node(comment_node_label, label=comment, shape="plaintext", color="#f80000")
        A.add_node(comment_node_label+"_invis", label="", width="0",height="0", style="invis")

        sg = A.add_subgraph([comment_node_label, comment_node_label+"_invis", start_node, ])

        sg.graph_attr['rank'] = 'same'

        A.add_edge(comment_node_label+"_invis", comment_node_label , "comment_{i}_0", style="invis")
        A.add_edge(start_node, comment_node_label+"_invis", "comment_{i}_1", style="dashed", color="#f88877", weight="100")
        # if end_node != start_node:
        #     A.add_edge(end_node, comment_node_label+"_invis", "comment_{i}_2", style = "dashed", color = "blue",weight="0.01")

    A.layout('dot')
    return A


# fl = ["a[10g], b[20g]", "a, b | P1|P2[1 h]|P3[220 C,2min] > c", "c[10g] | P4|P5 > d,e","a,b | P7> f"]
# ing, proc, edg, comments = parse_flow(fl)
# dag = render_graph(ing, proc, edg)
# dag.draw('viz.png')


def parse_metadata(lines):
    import yaml
    out = yaml.safe_load("\n".join(lines))
    return out

def parse_grc(path):
    with open(path) as f:
        fl = f.readlines()
    fl = [f.rstrip() for f in fl if f.rstrip()]

    metadata = []
    recipe = []
    while len(fl) > 0:
        l = fl.pop(0).strip()
        if l.startswith("----"):
            recipe = fl
            break
        metadata.append(l)
    assert len(recipe) > 0, "Either no recipe or no metadata"
    metadata = parse_metadata(metadata)
    ing, proc, edg, comments = parse_flow(recipe)
    g = make_nx_graph(ing, proc, edg)

    primary_ingredients =  {}
    for id, attrs in g.nodes(data=True):
        if attrs["type"] == "primary_ingredient":
            primary_ingredients[attrs["label"]] = attrs["amount"]
    dag = render_graph(g, comments)
    return dag, metadata, primary_ingredients




def latex_page(dag, metadata, primary_ingredients, pdf_path):
    template = r"""
    \section*{%s}
    \begin{tabular}{|l|r|}
    \hline
    \textbf{Ingredient}& \textbf{Amount}\\
    \hline
    %s
    \end{tabular}
   
    \begin{figure}[!b]
    \includegraphics[height=0.67\textheight,page=1]{%s}
    \end{figure}
    \newpage
    """
    prim_ingr = {k.replace("_", r"\_"): v for k, v in primary_ingredients.items()}
    table = "\n".join([f"{k}&{v} \\\\ \n \hline" for k,v in prim_ingr.items()])
    dag.draw(pdf_path)
    return template % (metadata["name"], table, pdf_path)

def latex_document(pages):
    template = r"""
\documentclass[10pt,a4paper]{book}
\usepackage{graphicx}
\begin{document}
%s
\end{document} 
    """
    return template % "\n".join(pages)

recipe_dir = "../recipes/"
pdf_dir = "graphs"

import glob
pages = []
for r in glob.glob(os.path.join(recipe_dir, "*.grc")):
    dag, metadata, prim_ings = parse_grc(r)
    output = os.path.join(pdf_dir, os.path.splitext(os.path.basename(r))[0] + ".pdf")
    p = latex_page(dag, metadata, prim_ings, output)
    # print(p)
    pages.append(p)
# assert len(pages) > 0
#
print(latex_document(pages))
# l2 = "carrot  |  peel "
# l3 = "carrot | peel > carrot"
#
#
#
#
# l1 = "carrot | peel | chop "
# l2 = "carrot | peel | chop > carrot"
# l = "carrot, aubergine | peel |chop >test"
# l = "carrot, aubergine | peel |chop "
# l = "carrot, aubergine[5g] | peel |chop[2mm] | cook[220C, 1h] > mix"




# print(m['processes'])
# print(m['outputs'])
# else:
# print("No match")
# re.match(r'\s*(?P<inputs>\w+))\s*=\s*(?P<rhs>\w+)\s*\((?P<args>.*)\)', l)


# input[amount], ... | process[arguments]| ... > output




#
# def parse_flow_line(line: str) -> Dict:
#     """
#     :param line:
#     :return:
#     """
#     pipe_sep = line.split("|")
#     assert len(pipe_sep) > 1, "Wrong format `|' needed"
#     inputs = {i.strip() for i in pipe_sep[0].split(',')}
#
#     chevron_sep = line.split(">")
#     assert len(chevron_sep) < 3, "more than one `>'"
#
#     if len(chevron_sep) == 2:
#         outputs = {o.strip() for o in chevron_sep[1].split(',')}
#         processes = pipe_sep[1:-1]
#     else:
#         outputs = inputs
#         processes = pipe_sep[1:]
#
#     for i in inputs:
#
#     return {"inputs": inputs,
#             "processes": processes,
#             "outputs": outputs}
#
