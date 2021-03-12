import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from collections import deque, namedtuple
from queue import PriorityQueue
import copy

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

building = namedtuple('Building', ['name', 'x', 'y'])
attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []
        # Out Additions
        self.p_queue = PriorityQueue()
        self.defence_priority_map = dict()
        self.should_thunder_strike = -1

        self.critical_turrets = []
        self.crtical_walls = []

        self.throw_interceptors = True
        
    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.first_strategy(game_state)

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def first_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """

        # Place attackers
        # self.place_attackers(game_state)
        
        # Queue defneces
        if(game_state.turn_number == 0):
            # Add the inital defences to queue.
            self.add_intial_defences_to_queue(game_state)
        else:
            self.queue_repair_of_critical(game_state)

        # Build defences
        self.build_defences(game_state)

        self.place_attackers(game_state)

    
    def add_intial_defences_to_queue(self, game_state):

        inital_turrets = [[3, 12], [24, 12], [11, 4], [16, 4]]
        inital_walls = [[3, 13], [24, 13], [7, 8], [20, 8]]
        self.critical_turrets += inital_turrets
        self.crtical_walls += inital_walls

        # Place these into the prioity queue.
        for turret in inital_turrets:
            self.p_queue.put((-1, building(name=TURRET, x=turret[0], y=turret[1])))
            self.p_queue.put((-1, building(name='upgrade', x=turret[0], y=turret[1])))
        for wall in inital_walls:
            self.p_queue.put((-1, building(name=WALL, x=wall[0], y=wall[1])))

        # Round 3
        next_walls = [[0, 13], [1, 13], [2, 13], [25, 13], [26, 13], [27, 13], [4, 12], [23, 12]]
        self.crtical_walls += next_walls
        for wall in next_walls:
            self.p_queue.put((-0.8, building(name=WALL, x=wall[0], y=wall[1])))

        # Round 5
        next_turrets = [[4, 11], [23, 11], [11, 5], [16, 5]]
        self.critical_turrets += next_turrets
        for turr in next_turrets:
            self.p_queue.put((-0.5, building(name=TURRET, x=turr[0], y=turr[1])))
            self.p_queue.put((-0.4, building(name='upgrade', x=turr[0], y=turr[1])))
        
        couples_walls = [[5, 11], [22, 11], [7, 9], [20, 9], [8, 8], [19, 8]]
        self.crtical_walls += couples_walls
        for wall in couples_walls:
            self.p_queue.put((-0.3, building(name=WALL, x=wall[0], y=wall[1])))

        next_3_turrets = [[6, 9], [21, 9]]
        self.critical_turrets += next_3_turrets
        next_3_walls = [[7, 10], [20, 10], [8, 8], [19, 8]]
        self.crtical_walls += next_3_walls
        for turr in next_3_turrets:
            self.p_queue.put((-0.1, building(name=TURRET, x=turr[0], y=turr[1])))
            self.p_queue.put((-0.02, building(name='upgrade', x=turr[0], y=turr[1])))
        for wall in next_3_walls:
            self.p_queue.put((-0.05, building(name=WALL, x=wall[0], y=wall[1])))

        upper_turrets = [[1, 12], [2, 12], [25, 12], [26, 12]]
        self.critical_turrets += upper_turrets
        for turr in upper_turrets:
            self.p_queue.put((-0.01, building(name=TURRET, x=turr[0], y=turr[1])))

        across_middle_walls = [[6, 10], [9, 7], [18, 7], [10, 6], [17, 6], [12, 5], [13, 5], [14, 5], [15, 5]]
        self.crtical_walls += across_middle_walls
        for wall in across_middle_walls:
            self.p_queue.put((-0.001, building(name=WALL, x=wall[0], y=wall[1])))


    def build_defences(self, game_state):
        number_placed = 1
        should_be_able_to_place = True
        # Takes what on p queue.
        while(not self.p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            defence_value, defence = self.p_queue.get()        # building object
            gamelib.debug_write("Popped off the queue: P_Value: {}  Item: {}".format(defence_value, defence))

            # Get the cost of the object if this is greater than the amount of SP points, then place back onto the queue and break.
            # Add this to the dictionary of defences to prioities.
            self.defence_priority_map[defence] = defence_value
            if defence_value > -0.25:
                self.throw_interceptors = False
            if defence_value < -0.#375:
                self.throw_interceptors = True


            # Need to careful here whether we decide to upgrade or build a new defence.
            if(defence.name == 'upgrade'):
                # should_be_able_to_place = True
                if(game_state.type_cost(unit_type=game_state.game_map[defence.x, defence.y][0].unit_type, upgrade=True)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                    # We cannot afford place back onto the queue and break.
                    self.p_queue.put((defence_value, defence))
                    break
                else:
                    number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                if(game_state.type_cost(unit_type=defence.name)[0] > game_state.get_resource(resource_type=SP, player_index=0)):
                    self.p_queue.put((defence_value, defence))
                    break
                else:
                    should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                    number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
                    if(number_placed==0 and should_be_able_to_place):
                        self.p_queue.put((defence_value, defence))
                        gamelib.debug_write("An error has occured here, where we should have been able to place and had credit but didn't. If so break the loop.")
                        break

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(defence.name, defence.x, defence.y, number_placed))


    


    def queue_repair_of_critical(self, game_state):

        current_stationary_units = self.get_current_stationary_units(game_state)

        # Loop through the critical objects, if we cannot find then 
        for item in self.crtical_walls:
            if building(name=WALL, x=item[0], y=item[1]) not in current_stationary_units:
                # Look for it in the map.
                gamelib.debug_write(self.defence_priority_map)
                value = self.defence_priority_map.get(building(name=WALL, x=item[0], y=item[1]), 0)
                gamelib.debug_write("Placing back into prioity queue: {}".format(value))
                self.p_queue.put((value, building(name=WALL, x=item[0], y=item[1])))

        for item in self.critical_turrets:
            if building(name=TURRET, x=item[0], y=item[1]) not in current_stationary_units:
                value = self.defence_priority_map.get(building(name=TURRET, x=item[0], y=item[1]), 0)
                gamelib.debug_write("Placing back into prioity queue: {}".format(value))
                self.p_queue.put((value, building(name=TURRET, x=item[0], y=item[1])))


    def get_current_stationary_units(self, game_state):
        '''
        returns a list of our stationary units in the form [type, [location_x, location_y]]
        Used for keeping track of what was destroyed in the previous round
        '''
        stationary_units = set()
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 0:
                        stationary_units.add((unit.unit_type, location[0], location[1]))
        return stationary_units
    
    ''' 
    --------------------------------------------------------
    Attack Code.
    --------------------------------------------------------
    '''


    def place_attackers(self, game_state):

        if game_state.contains_stationary_unit([7, 8]) and game_state.contains_stationary_unit([20, 8]):
            self.throw_interceptors = False
        
        if self.throw_interceptors:
            game_state.attempt_spawn(INTERCEPTOR, [21, 7], num=1)
            game_state.attempt_spawn(INTERCEPTOR, [6, 7], num=1)
        

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
