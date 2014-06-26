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
            self.known_positions.append(self.last_position)

            self.datatargets['pos_x'] = 0
            self.datatargets['pos_y'] = 0
            self.set_datatarget_feedback('pos_x', 0)
            self.set_datatarget_feedback('pos_y', 0)

            self.datasources['pos_x'] = self.position[0]
            self.datasources['pos_y'] = self.position[1]
            self.datasources['ground'] = self.perceive_ground()
            self.select_motive() # also sets datasource

    def perceive_ground(self):
        return self.world.get_ground_at(self.position[0], self.position[1])

    def update(self):
        """called on every world simulation step to advance the life of the agent"""

        target_pos_x = int(self.datatargets['pos_x'])
        target_pos_y = int(self.datatargets['pos_y'])
        self.set_datatarget_feedback('pos_x', target_pos_x)
        self.set_datatarget_feedback('pos_y', target_pos_y)

        # TODO: improve movement behavior
        if not target_pos_x and not target_pos_y:
            # a very simple random movement to check how a position update cycle works
            random.seed(os.urandom(32))
            newpos = (self.position[0]+random.randint(-5, 5), self.position[1]+random.randint(-5, 20))
        else:
            # locomote to desired position
            newpos = (target_pos_x, target_pos_y)

        # use water as a border and respect motives
        motive = self.select_motive()
        if self.world.get_ground_at(newpos[0], newpos[1]) != 7 and motive == 'exploration' or motive == 'energy':
            self.known_positions.append(self.last_position)
            self.last_position = self.position
            self.position = newpos
            self.datasources['moved'] = 1
            self.datasources['pos_x'] = newpos[0]
            self.datasources['pos_y'] = newpos[1]
        else:
            self.datasources['moved'] = 0
            self.datasources['pos_x'] = self.position[0]
            self.datasources['pos_y'] = self.position[1]

        self.datasources['ground'] = self.perceive_ground()

        self.update_tanks()
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

    def observe(self):
        print('Ground:', ground_types[self.perceive_ground()]['type'])
        print('Energy:', self.energy)
        print('Healthiness:', self.healthiness)
        print('Exploration:', self.exploration)
        print('Motive:', self.select_motive(), '\n')