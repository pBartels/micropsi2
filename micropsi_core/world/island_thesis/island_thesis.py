from micropsi_core.world.island.island import *
import random, collections

class ThesisIsland(Island, World):
    def __init__(self, filename, world_type="ThesisIsland", name="", owner="", uid=None, version=1):

        self.assets['background'] = "island/psi_emo.png"

        self.supported_worldadapters.append("ThesisAgent")

        self.groundmap.update({'image': "psi_emo.png",
                               'start_position': (700, 400),
                               'scaling': (3.125, 3.125),
        })

        # delegate constructor call to parent class
        super().__init__(filename, world_type, name, owner, uid, version)


class ThesisAgent(WorldAdapter):
    datasources = {'moved': 0, 'pos_x': 0, 'pos_y': 0, 'ground': 0, 'motive': 0}
    datatargets = {'pos_x': 0, 'pos_y': 0}
    last_position = None
    known_positions = []

    # the tanks
    energy = 1.0
    healthiness = 1.0
    exploration = 0.5

    def __init__(self, world, uid=None, **data):
        super(ThesisAgent, self).__init__(world, uid, **data)

    def initialize_worldobject(self, data):
        if not "position" in data:
            self.position = self.world.groundmap['start_position']
            self.last_position = self.position
            self.known_positions.append(self.position)

            self.datatargets['pos_x'] = 0
            self.datatargets['pos_y'] = 0
            self.set_datatarget_feedback('pos_x', 0)
            self.set_datatarget_feedback('pos_y', 0)

            self.datasources['pos_x'] = self.position[0]
            self.datasources['pos_y'] = self.position[1]
            self.datasources['ground'] = self.perceive_ground()
            self.select_motive() # also sets datasource

    def perceive_ground(self):
        return self.world.get_ground_at(self.datasources['pos_x'], self.datasources['pos_y'])

    def update(self):
        """called on every world simulation step to advance the life of the agent"""
        self.locomote()
        self.update_tanks()

        self.datasources['ground'] = self.perceive_ground()

        self.observe()

    def update_tanks(self):
        """called on every world simulation step to handle the tank system"""

        ground = self.perceive_ground()
        if ground == 3: # darkgrass (food area)
            self.energy += 0.1
        elif ground == 2: # swamp (dangerous area)
            self.healthiness -= 0.1
        elif ground == 0: # grass (healing area)
            self.healthiness += 0.1
        elif ground == 1: # sand (basic ground)
            pass

        # tank decay mechanisms
        self.energy -= 0.001 # energy empties constantly on a slow rate
        self.exploration -= 0.001 # exploration tank empties constantly on a slow rate

        if self.position != self.last_position:
            self.energy -= 0.01 # energy empties faster when moving around

        if self.position not in self.known_positions:
            self.exploration += 0.01 # exploration tank refills when moving around

    def select_motive(self):
        # it might be useful to put everything in a dict in general?
        tanks = collections.OrderedDict([('energy', self.energy),
            ('healthiness', self.healthiness),
            ('exploration', self.exploration),
        ])
        motive = min(tanks, key=tanks.get)
        self.datasources['motive'] = list(tanks.keys()).index(motive)
        return motive

    def locomote(self):
        target_pos_x = int(self.datatargets['pos_x'])
        target_pos_y = int(self.datatargets['pos_y'])
        self.set_datatarget_feedback('pos_x', target_pos_x)
        self.set_datatarget_feedback('pos_y', target_pos_y)

        if target_pos_x and target_pos_y and (self.position[0] != target_pos_x or self.position[1] != target_pos_y):
            # move towards target
            diff_x = max(min(5, target_pos_x - self.position[0]), -5)
            diff_y = max(min(5, target_pos_y - self.position[1]), -5)
            newpos_x = int(self.position[0] + diff_x)
            newpos_y = int(self.position[1] + diff_y)

            # validate new position is not on water or sample new local position around it if so
            random.seed(os.urandom(32))
            newpos_x_s = newpos_x
            newpos_y_s = newpos_y
            iterations = 0
            while self.world.get_ground_at(newpos_x_s, newpos_y_s) == 7:
                iterations += 1
                newpos_x_s = int(newpos_x + random.randint(-10, 10))
                newpos_y_s = int(newpos_y + random.randint(-10, 10))

                if iterations >= 4:
                    self.datasources['moved'] = 0 # leads to sampling of new target
                    return

            # update position
            self.last_position = self.position
            self.position = (newpos_x_s, newpos_y_s)
            self.known_positions.append(self.position)
            self.datasources['moved'] = 1
        else:
            self.datasources['moved'] = 0

        self.datasources['pos_x'] = self.position[0]
        self.datasources['pos_y'] = self.position[1]

    def observe(self):
        print('Ground:', ground_types[self.perceive_ground()]['type'])
        print('Energy:', self.energy)
        print('Healthiness:', self.healthiness)
        print('Exploration:', self.exploration)
        print('Motive:', self.select_motive())

        print('Position:', self.position[0], self.position[1])
        print('Target:', self.datatargets['pos_x'], self.datatargets['pos_y'])
        print('Moved:', bool(self.datasources['moved']))

        print('\n')