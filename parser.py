import re
import networkx as nx
import dot2tex
from networkx.drawing.nx_agraph import to_agraph


#
#
# def parse_grc():
#     lines = s.split('\n')
#     from collections import OrderedDict
#     ingredients = OrderedDict()
#     start = 0
#     for e, k in enumerate(lines):
#         start = e
#         l = k.rstrip()
#         if l.startswith("-"):
#             break
#         if l:
#             i, amount = l.split(":")
#             ingredients[i] = amount
#
#     G = nx.DiGraph()
#     synonym_last_occurences = {}
#     for i in ingredients.keys():
#         G.add_node(i, label=i)
#         synonym_last_occurences[i] = i
#
#     for i, k in enumerate(lines[start + 1:]):
#         l = k.rstrip()
#         if l:
#             # m = re.findall(r'\([^()]*\)', l)
#             m = re.match(r'(?P<t>\d+\.)\s+(?P<lhs>\w+)\s*=\s*(?P<rhs>\w+)\s*\((?P<args>.*)\)', l)
#             args = [a.strip() for a in m['args'].split(',')]
#             for a in args:
#                 assert a in synonym_last_occurences, f"{a} not in products/ingredients"
#
#             t = int(float(m['t']))
#             process_label = f"{m['rhs']}-{k}"
#             product_label = f"{m['lhs']}-{i}"
#
#             G.add_node(process_label, label=m['rhs'], shape="square")
#             G.add_node(product_label, label=m['lhs'])
#             for a in args:
#                 node_id = synonym_last_occurences[a]
#                 G.add_edge(node_id, process_label)
#
#             synonym_last_occurences[m['lhs']] = f"{m['lhs']}-{i}"
#             G.add_edge(process_label, product_label)
#
#             if m['lhs'] not in synonym_last_occurences:
#                 synonym_last_occurences[m['lhs']] = m['lhs']
#
#     A = to_agraph(G)
#     A.layout('dot')
#     A.draw('test1.png')


def parse_ingredients():
    pass
def parse_flow():
    pass


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
    m = re.match(r'\s*(?P<inputs>[\w,\s\[\]]+)\s*\|\s*(?P<processes>[\w\s\|\[\]\,]+)\s*(>\s*(?P<outputs>.*))?', l)
    assert m, f"Error parsing {l}"

    inputs = [parse_ingredient(i) for i in m['inputs'].split(',')]

    if m['outputs'] is None:
        outputs = inputs
    else:
        outputs = [parse_ingredient(i) for i in m['outputs'].split(',')]

    processes = [parse_process(i) for i in m['processes'].split('|')]

    return {"inputs": inputs,
            "processes": processes,
            "outputs": outputs,
            }
