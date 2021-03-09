import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from collections import deque, namedtuple
from queue import PriorityQueue

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

    
        # Build defences
        self.build_defences(game_state)

    
    def add_intial_defences_to_queue(self, game_state):

        inital_turrets = [[3, 13], [24, 13], [4, 12], [22, 12], [21, 11], [22, 11], [19, 9], [20, 9], [23, 12]]
        inital_walls = [[2, 13], [3, 12], [4, 11], [5, 10], [6, 9], [7, 8], [19, 8], [8, 7], [18, 7], [9, 6], [17, 6], [10, 5], [16, 5], [11, 4], [15, 4], [12, 3], [13, 3], [14, 3], [0, 13], [1, 13], [25, 13], [26, 13], [27, 13]]

        # Place these into the prioity queue.
        for turret in inital_turrets:
            self.p_queue.put((-1, building(name=TURRET, x=turret[0], y=turret[1])))
        for wall in inital_walls:
            self.p_queue.put((-1, building(name=WALL, x=wall[0], y=wall[1])))


    def build_defences(self, game_state):
        number_placed = 1
        self.updated_p_queue = PriorityQueue()
        # Takes what on p queue.
        while(not self.p_queue.empty() and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            defence_value, defence = self.p_queue.get()        # building object
            gamelib.debug_write("Popped off the queue: P_Value: {}  Item: {}".format(defence_value, defence))

            # Add this to the dictionary of defences to prioities.
            self.defence_priority_map[defence] = defence_value

            # Need to careful here whether we decide to upgrade or build a new defence.
            if(defence.name == 'upgrade'):
                should_be_able_to_place = True
                number_placed = game_state.attempt_upgrade([defence.x, defence.y])
            else: 
                should_be_able_to_place = game_state.can_spawn(defence.name, [defence.x, defence.y])
                number_placed = game_state.attempt_spawn(defence.name, [defence.x, defence.y])
            
            if number_placed == 0 and should_be_able_to_place:
                # Need to add back into the queue if we failed to build this.
                self.updated_p_queue.put((defence_value, defence))

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(defence.name, defence.x, defence.y, number_placed))
        self.p_queue = self.updated_p_queue

    
    ''' 
    --------------------------------------------------------
    Attack Code.
    --------------------------------------------------------
    '''

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
