#!/usr/bin/env python3

import networkx as nx			# Abstract network operations

g = nx.Graph()
for ll in """
0 1 36
1 0 2 37
2 1 3 21 38
3 2 4 22 39
4 3 5 23 40
5 4 6 24 41
6 5 25
7 8 43
8 7 9 44
9 8 10 28 45
10 9 11 29 46
11 10 12 30 47
12 11 13 31 48
13 12 32
14 15 50
15 14 16 51
16 15 17 35 52
17 16 18 36 53
18 17 19 37 54
19 18 20 38
20 19 39
21 22 2
22 21 23 3
23 22 24 42 4
24 23 25 43 5
25 24 26 44 6
26 25 27 45
27 26 46
28 29 9
29 28 30 10
30 29 31 49 11
31 30 32 50 12
32 31 33 51 13
33 32 34 52
34 33 53
35 36 16
36 35 37 0 17
37 36 38 1 18
38 37 39 2 19
39 38 40 3 20
40 39 41 4
41 40 5
42 43 23
43 42 44 7 24
44 43 45 8 25
45 44 46 9 26
46 45 47 10 27
47 46 48 11
48 47 12
49 50 30
50 49 51 14 31
51 50 52 15 32
52 51 53 16 33
53 52 54 17 34
54 53 18
""".splitlines():
	d = [int(x) for x in ll.split()]
	for dd in d[1:]:
		g.add_edge(d[0], dd)
'''
0 1 3
1 0 2 4
2 1 5
3 0 4 6
4 1 3 5 7
5 2 4 8
6 3 7
7 4 6 8
8 5 7
'''
def find_mesh(p_graph, size):
	cells = {}
	for node_a in p_graph.nodes:
		for node_b in p_graph.neighbors(node_a):
			for node_c in [_ for _ in p_graph.neighbors(node_b) if _ != node_a]: # Avoid back to start immediately
				for node_d in [_ for _ in p_graph.neighbors(node_c) if not (_ == node_b or _ == node_a)]: # Avoid length 2 or 3 paths back
					# Check if d connects back to a and the cycle length is 4
					if node_d in p_graph.neighbors(node_a): # and len({node_a, node_b, node_c, node_d}) == 4:
						cell = [node_a, node_b, node_c, node_d]
						cell_s = tuple(sorted(cell))						# Key on canonical representation (sorted tuple) to avoid duplicates.
						cells[cell_s] = cell
	return list(cells.values())

m1 = find_mesh(g, 4)
m2 = [x for x in nx.minimum_cycle_basis(g) if len(x) == 4]
print(len(m1), m1)
print(len(m2), m2)

'''

	def find_mesh(g, size):
		def next_node():
			return [n for n in g.neighbors(nn[-1]) if n not in nn]

		cells = {}
		vs = [[ns] for ns in g.nodes]:						# Any node can be the vertex of a mesh.
		for i in range(size - 1):									# Look for more to make requested size.
				for n in g.neighbors(vs[-1]):
					if n not in vs:
						vss.append
				vs .append()
'''
