__author__ = 'pBartels'

import re, math, random, os


def path_planning(netapi, node=None, sheaf='default', **params):

    def determine_nearest_waypoint(node, pos_x, pos_y):
        """ Returns the waypoint nearest to pos_x, pos_y on the paths leading to the goal given by 'node' """

        # get all connected paths to this ground marker
        sur_paths = [link.target_node for link in node.get_gate('sur').outgoing.values()]

        # traverse path and determine nearest waypoint
        nearest_waypoint = None
        nearest_waypoint_distance = None
        for w in sur_paths:
            cur_waypoint = w

            while cur_waypoint:
                match = list(map(int, re.findall(r'\d+', cur_waypoint.name)))
                distance = math.sqrt((pos_x - match[0]) ** 2 + (pos_y - match[1]) ** 2)

                if distance < 1:
                    # already next to nearest waypoint, now follow path (in 'por' direction)
                    next_waypoints = [link.target_node for link in cur_waypoint.get_gate('por').outgoing.values()]
                    if next_waypoints:
                        return next_waypoints[0]

                if nearest_waypoint_distance == None or distance < nearest_waypoint_distance:
                    nearest_waypoint = cur_waypoint
                    nearest_waypoint_distance = distance

                # get next waypoint in path
                next_waypoints = [link.target_node for link in cur_waypoint.get_gate('ret').outgoing.values()]
                if next_waypoints:
                    cur_waypoint = next_waypoints[0]
                else:
                    break # reached end of path

        return nearest_waypoint


    def validate_waypoint_leads_to_goal(waypoint_node, goal_node):
        """ Validates if the waypoint_node leads to the goal_node """

        cur_waypoint = waypoint_node
        while cur_waypoint:
            sur_node_names = [link.target_node.name for link in cur_waypoint.get_gate('sub').outgoing.values()]
            if sur_node_names and goal_node.name in sur_node_names:
                return True

            cur_waypoint = [link.target_node for link in cur_waypoint.get_gate('por').outgoing.values()]
            if cur_waypoint:
                cur_waypoint = cur_waypoint[0]

        return False


    def get_nodes_by_name(nodespace, name):
        """ Returns all nodes in the 'nodespace' with the name given by 'name' """
        return [n for n in netapi.get_nodes(nodespace.uid) if n.name == name]


    # NOTE: the gates of the sensors must be properly parameterized (the maximum must not be 1)
    pos_x = int(node.get_slot('pos_x').get_activation())
    pos_y = int(node.get_slot('pos_y').get_activation())
    motive = int(node.get_slot('motive').get_activation())
    moved = int(node.get_slot('moved').get_activation())
    target_x = int(node.get_slot('target_x').get_activation())
    target_y = int(node.get_slot('target_y').get_activation())

    # check if a dedicated nodespace already exists and use this
    path_nodespace = None
    for n in netapi.nodespaces.values():
        if n.name == 'mapping':
            path_nodespace = n
            break


    # calculate a target that fulfills the current demand
    if path_nodespace and (motive == 0 or motive == 1):
        # pepare a dict of all nodes in the path nodespace
        nodes = {n.name:get_nodes_by_name(path_nodespace, n.name) for n in netapi.get_nodes(path_nodespace.uid)}

        # TODO: there might be better solutions to encode motives?
        # motive encoding:
        # 0. 'energy'
        # 1. 'healthiness'
        # 2. 'exploration'

        # determine a goal node that fulfills demand
        if motive == 0: # 0. 'energy'
            marker_node = nodes['ground_darkgrass'][0]
        elif motive == 1: # 1. 'healthiness'
            marker_node = nodes['ground_grass'][0]

        # check if current target already leads to an according goal node
        target_waypoint_name = "waypoint_%s_%s" % (target_x, target_y)
        waypoint_leads_to_goal = False
        for n in get_nodes_by_name(path_nodespace, target_waypoint_name):
            waypoint_leads_to_goal = validate_waypoint_leads_to_goal(n, marker_node)
            if waypoint_leads_to_goal:
                break

        # determine nearest waypoint in all paths to area that fulfills demand
        if not waypoint_leads_to_goal:
            nearest_waypoint = determine_nearest_waypoint(marker_node, pos_x, pos_y)
            if nearest_waypoint:
                match = list(map(int, re.findall(r'\d+', nearest_waypoint.name)))
                target_x, target_y = match

    
    if target_x and target_y and target_x == pos_x and target_y == pos_y:
        # agent has reached targeted position
        # reset target
        target_x, target_y = (0, 0)

    elif target_x and target_y and moved:
        # agent targets a position but hasn't reached it yet
        # do not change it, let the agent move towards it
        pass

    elif not target_x or not target_y or not moved:
        # agent targets no position at the moment
        # decide new target (at the moment not based on the motive)
        # (even if a motive, for example 'energy', would be known, if no target is set, it is not known how to
        # fulfill it and thus a random movement seems useful)

        # sample a random position on the map
        random.seed(os.urandom(32))
        # TODO use proper world dimensions
        while True:
            target_x, target_y = (random.randint(0, 799), random.randint(0, 799))
            if netapi.world.get_ground_at(target_x, target_y) != 7: # validate target is not on water
                break

    # set activation on gates to enable locomotion
    node.get_gate("target_x").gate_function(target_x)
    node.get_gate("target_y").gate_function(target_y)


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
    perceived_ground = int(node.get_slot('ground').get_activation())
    if perceived_ground == 3:
        ground_node = ground_darkgrass
    elif perceived_ground == 2:
        ground_node = ground_swamp
    elif perceived_ground == 0:
        ground_node = ground_grass
    else:
        ground_node = None

    ground_at = netapi.world.get_ground_at(pos_x, pos_y)
    if ground_node and perceived_ground == ground_at and not get_waypoints_in_range(ground_node, pos_x, pos_y, 3):
        netapi.link(waypoint, 'sub', ground_node, 'gen')
        netapi.link(ground_node, 'sur', waypoint, 'gen')
        netapi.unlink(last_waypoint, 'sub', waypoint, 'gen') # unlink the waypoint marker

        if perceived_ground == 2:
            remove_preceding_waypoints(waypoint)


    # weaken the links in the current path on each step
    last_waypoint_ids = last_waypoint.get_associated_node_ids()
    if last_waypoint_ids:
        last_waypoint_node = netapi.get_node(last_waypoint_ids[0])
        weaken_waypoint_links(last_waypoint_node, 0.01)


    # TODO nodes that model linear movements (?) should be removed if some threshold is reached

    # TODO if a demand was very high when it is fulfilled, the path should be stored as longer?

    # TODO waypoint optimization

    # TODO if the agent leaves an area it could also remember the way back to it

    # TODO do not add two times the same waypoint one after another
