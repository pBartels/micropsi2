__author__ = 'pBartels'
__date__ = '20.06.14'

import re


def mapping(netapi, node=None, sheaf='default', **params):

    def remove_preceding_waypoints(waypoint, delete_self=False):
        """ Removes recursively all preceding waypoints in the path (ret-link) for the given waypoint """

        waypoints = [link.target_node for link in waypoint.get_gate('ret').outgoing.values()]
        for w in waypoints:
            remove_preceding_waypoints(w, True)

        if delete_self:
            # unlink or remove x and y position nodes
            pos_nodes = [link.target_node for link in waypoint.get_gate('sub').outgoing.values()]
            for n in pos_nodes:
                if len(n.get_gate('sub').outgoing) > 1:
                    netapi.unlink(waypoint, 'sub', n, 'gen')
                    netapi.unlink(n, 'sur', waypoint, 'gen')
                else:
                    netapi.delete_node(n)

            netapi.delete_node(waypoint)


    def get_waypoints_in_range(node, pos_x, pos_y, radius):
        """ Returns all connected waypoint nodes inside the given radius around pos_x and pos_y """

        nodes = []
        for uid in node.get_associated_node_ids():
            n = netapi.get_node(uid)
            match = list(map(int, re.findall(r'\d+', n.name)))
            if match and pos_x + radius > match[0] > pos_x - radius and pos_y + radius > match[1] > pos_y - radius:
                nodes.append(n)

        return nodes


    def weaken_waypoint_links(waypoint, decay):
        """ Weakens recursively the links between the waypoint nodes (por/ret links) to introduce forgetfulness"""

        ret_links = [link for link in waypoint.get_gate('ret').outgoing.values()]
        for l in ret_links + ret_links:
            weaken_waypoint_links(l.target_node, decay)
            l.weight = l.weight - decay
            if l.weight <= 0:
                remove_preceding_waypoints(l.target_node, True)


    # TODO: use slots for actors instead of the 'moved signal'...
    if not node.get_slot('moved').get_activation():
        return


    # check if a dedicated nodespace already exists and use this or create one
    path_nodespace = None
    for n in netapi.nodespaces.values():
        if n.name == 'mapping':
            path_nodespace = n
            break

    if not path_nodespace:
        path_nodespace = netapi.create_node("Nodespace", node.parent_nodespace, 'mapping')


    # pepare a dict of all nodes in the path nodespace
    nodes = {n.name:n for n in netapi.get_nodes(path_nodespace.uid)}


    # note: the gates of the sensors must be properly parameterized (the maximum must not be 1)
    pos_x = int(node.get_slot('pos_x').get_activation())
    pos_y = int(node.get_slot('pos_y').get_activation())


    # check if a pointer to the last waypoint already exists, if not create one
    if 'last_waypoint' in nodes:
        last_waypoint = nodes['last_waypoint']
    else:
        last_waypoint = netapi.create_node("Concept", path_nodespace.uid, 'last_waypoint')


    # create a concept node for each step (locomotion) the agent actually performs
    waypoint_name = "waypoint_%d_%d" % (pos_x, pos_y)
    waypoint = netapi.create_node("Concept", path_nodespace.uid, waypoint_name)


    # create por/ret connections between the waypoints
    last_waypoint_ids = last_waypoint.get_associated_node_ids()
    if last_waypoint_ids:
        last_waypoint_node = netapi.get_node(last_waypoint_ids[0])
        netapi.link(last_waypoint_node, "por", waypoint, 'gen')
        netapi.link(waypoint, "ret", last_waypoint_node, 'gen')
        netapi.unlink(last_waypoint, 'sub', last_waypoint_node, 'gen') # unlink the waypoint marker


    # link last waypoint marker to new waypoint
    netapi.link(last_waypoint, "sub", waypoint, 'gen')


    # create for the positions two other concept nodes which are connected with sub/sur
    # use the sub connection weight to encode the position
    waypoint_x_name = "waypoint_x_%d" % (pos_x)
    if waypoint_x_name in nodes:
        waypoint_x = nodes[waypoint_x_name]
    else:
        waypoint_x = netapi.create_node("Concept", path_nodespace.uid, waypoint_x_name)
    netapi.link(waypoint, 'sub', waypoint_x, 'gen', weight=pos_x)
    netapi.link(waypoint_x, 'sur', waypoint, 'gen')

    waypoint_y_name = "waypoint_y_%d" % (pos_y)
    if waypoint_y_name in nodes:
        waypoint_y = nodes[waypoint_y_name]
    else:
        waypoint_y = netapi.create_node("Concept", path_nodespace.uid, waypoint_y_name)
    netapi.link(waypoint, 'sub', waypoint_y, 'gen', weight=pos_y)
    netapi.link(waypoint_y, 'sur', waypoint, 'gen')


    # check if the concept nodes for ground types are already existing or create them
    if 'ground_darkgrass' not in nodes: # darkgrass (3, food area)
        ground_darkgrass = netapi.create_node("Concept", path_nodespace.uid, 'ground_darkgrass')
    else:
        ground_darkgrass = nodes['ground_darkgrass']

    if 'ground_swamp' not in nodes: # swamp (2, dangerous area)
        ground_swamp = netapi.create_node("Concept", path_nodespace.uid, 'ground_swamp')
    else:
        ground_swamp = nodes['ground_swamp']

    if 'ground_grass' not in nodes: # grass (0, healing area)
        ground_grass = netapi.create_node("Concept", path_nodespace.uid, 'ground_grass')
    else:
        ground_grass = nodes['ground_grass']


    # attach the path to a ground_type / area if not already a nearby waypoint is linked
    # TODO: the agent should also remember world borders?!
    ground = int(node.get_slot('ground').get_activation())
    if ground == 3:
        ground_node = ground_darkgrass
    elif ground == 2:
        ground_node = ground_swamp
    elif ground == 0:
        ground_node = ground_grass
    else:
        ground_node = None

    if ground_node and not get_waypoints_in_range(ground_node, pos_x, pos_y, 15):
        netapi.link(waypoint, 'sub', ground_node, 'gen')
        netapi.link(ground_node, 'sur', waypoint, 'gen')
        netapi.unlink(last_waypoint, 'sub', waypoint, 'gen') # unlink the waypoint marker

        if ground == 2:
            remove_preceding_waypoints(waypoint)


    # weaken the links in the current path on each step
    last_waypoint_ids = last_waypoint.get_associated_node_ids()
    if last_waypoint_ids:
        last_waypoint_node = netapi.get_node(last_waypoint_ids[0])
        weaken_waypoint_links(last_waypoint_node, 0.01)


    # TODO nodes that model linear movements (?) should be removed if some threshold is reached

    # TODO if a demand was very high when it is fulfilled, the path should be stored as longer?

    # TODO waypoint optimization
