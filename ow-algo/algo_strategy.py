import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from collections import deque, namedtuple
import random

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


class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

        # Add in a queue of things which should be built.
        '''
        structure_queue: deque[building]. Holds the structure we want to build. Deqeue as we can prepend
        when we need to fix up defenses, and 
        building: namedtuple. Structure for holding instructions on what to build.
                  name - wall, turrent etc
                  x / y - coordinates
        '''

        


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
        self.enum_to_index_map = {WALL: 0, SUPPORT: 1, TURRET: 2, SCOUT:3, DEMOLISHER:4, INTERCEPTOR:5}
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

        # Set up queue for what we could attempt to spawn as structures.
        self.structure_queue = deque()
        # Walls first
        wall_list = [[0, 13], [1, 13], [2, 13], [25, 13], [26, 13], [27, 13], [3, 12], [24, 12], [4, 11], [23, 11], [5, 10], [22, 10], [6, 9], [21, 9], [7, 8], [20, 8], [8, 7], [19, 7]]
        for [x1,y1] in wall_list:
            self.structure_queue.append(building(name=WALL, x=x1, y=y1))

        turrent_list = [[6, 12], [21, 12], [8, 10], [12, 10], [15, 10], [19, 10], [10, 8], [17, 8], [12, 5], [15, 5]]
        for [x1,y1] in turrent_list:
            self.structure_queue.append(building(name=TURRET, x=x1, y=y1))

        # Recording of which building we had in the previous iteration.
        self.last_round_stationary_units = []


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

        self.starter_strategy(game_state)

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    # TODO - Need to figure out how to do 
    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """  
        gamelib.debug_write('Performing starter stratergy {} of your custom algo strategy'.format(game_state.turn_number))
        if game_state.turn_number == 0:
            self.build_intial_defences(game_state)

        if game_state.turn_number % 2 == 0:
            self.clever_scouts(game_state)

        if game_state > 0:
            self.find_destroyed_buildings(game_state)
        
        # Last call of the round which is used to figure out what was destroyed.
        self.last_round_stationary_units = self.get_current_stationary_units(game_state)




    def build_intial_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Get my own points.
        total_structural_credits = game_state.get_resource(resource_type=SP, player_index=0)
        gamelib.debug_write('Total credits: {}'.format(total_structural_credits))
        gamelib.debug_write('Queue size: {}'.format(len(self.structure_queue)))

        while(len(self.structure_queue) > 0 and total_structural_credits > 0):
            placement = self.structure_queue.popleft()
            number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). SP left: {}'.format(placement.name, placement.x, placement.y, total_structural_credits))
            if number_placed == 1:
                # Find the cost from the config info.
                total_structural_credits -= self.config["unitInformation"][self.enum_to_index_map[placement.name]]["cost1"]
    
    def rebuild_lost_defenses(self, game_state):

        rebuild_list = self.find_destroyed_buildings(game_state)
        for item in rebuild_list:
            self.structure_queue.appendleft(building(name=item[0], x=item[1][0], y=item[1][1]))



    def update_defences(self, game_state):
        '''
        uses the queue to execute the building of the new defenses.
        The ideas is to have one function reponible for building defenses, rather than several, so helper functions add to the queue, and hand over to this function to execute
        + allows for easier to plan a little
        '''
        total_structural_credits = game_state.get_resource(resource_type=SP, player_index=0)
        while(len(self.structure_queue) > 0 and total_structural_credits > 4):
            placement = self.structure_queue.popleft()
            number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). SP left: {}'.format(placement.name, placement.x, placement.y, total_structural_credits))
            if number_placed == 1:
                # Find the cost from the config info.
                total_structural_credits -= self.config["unitInformation"][self.enum_to_index_map[placement.name]]["cost1"]




    def clever_scouts(self, game_state):

        # Figure out how many sprits we can form.
        units_at_each_location = int(game_state.number_affordable(SCOUT) / 2)
        # List of where we can spawn our sprites as must be on an outer edge.
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        allowed_locations = self.filter_blocked_locations(friendly_edges, game_state)
        # Pick the best two from expected damage.
        best_two_locations = self.least_damage_spawn_locations(game_state=game_state, location_options=allowed_locations, number_of_returns=2)

        game_state.attempt_spawn(SCOUT, locations=best_two_locations, num=units_at_each_location)


    # ----------------------------------------------------------------
    # HELPER FUNCTIONS
    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    
    def get_current_stationary_units(self, game_state):
        '''
        returns a list of our stationary units in the form [type, [location_x, location_y]]
        Used for keeping track of what was destroyed in the previous round
        '''
        stationary_units = []
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 0:
                        stationary_units.append(unit.unit_type, location)
        return location
                        

    def find_destroyed_buildings(self, game_state):
        ''' 
        returns locations and what was destroyed in the form [type, [location_x, location_y]]
        Used to figure out what was lost between this round and the last round.
        '''
        current_stationary_units = self.get_current_stationary_units(game_state)
        return set(self.last_round_stationary_units) - set(current_stationary_units)


    def least_damage_spawn_locations(self, game_state, location_options, number_of_returns):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        location_damage_map = {}
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy turrets that can attack each location and multiply by turret damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i

            location_damage_map[location] = damage

        # Sort by the values in decendending order, get the first N many values and then get the locations of these.
        return [y[0] for y in sorted(location_damage_map.items(), key=lambda x: x[1])[0:number_of_returns]]
  





    # ----------
    # DO NOT EDIT
    # ----------    

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
