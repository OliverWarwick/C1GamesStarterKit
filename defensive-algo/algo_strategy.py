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
        # Varible to track whether we are in a state to play thunder or not. -1 = not ready/reset state , 0 = ready, 1 = played.
        self.play_thunder = -1

        # Set up queue structure
        '''
        structure_queue: deque[building]. Holds the structure we want to build. Deqeue as we can prepend
        when we need to fix up defenses. Also can be used for upgrades.
        building: namedtuple. Structure for holding instructions on what to build.
                  name - wall, turrent, upgrade. 
                  x / y - coordinates
        Any function using this will need to deal with the case where we have upgrades.
        '''
        self.structure_queue = deque()

        # Walls first
        wall_list = [[0, 13], [25, 13], [26, 13], [27, 13], [24, 12], [2, 11], [23, 11], [3, 10], [4, 9], [21, 9], [5, 8], [20, 8], [6, 7], [19, 7], [7, 6], [18, 6], [8, 5], [17, 5], [9, 4], [16, 4], [10, 3], [11, 3], [12, 3], [13, 3], [14, 3], [15, 3]]
        for [x1,y1] in wall_list:
            self.structure_queue.append(building(name=WALL, x=x1, y=y1))

        turrent_list = [[1, 12], [2, 12], [22, 12], [23, 12], [22, 11]]
        for [x1,y1] in turrent_list:
            self.structure_queue.append(building(name=TURRET, x=x1, y=y1))

        support_list = [[14, 2]]
        for [x1,y1] in support_list:
            self.structure_queue.append(building(name=SUPPORT, x=x1, y=y1))

        self.base_defences = [building(name=WALL, x=ele[0], y=ele[1]) for ele in wall_list] + [building(name=TURRET, x=ele[0], y=ele[1]) for ele in turrent_list]

        # Recording of which building we had in the previous iteration.
        ''' Has the form set(tuple(name, x, y)) so these need unpacking when using - needs to be this way so we can hash the elements unlike lists. '''
        self.last_round_stationary_units = set()

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

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        gamelib.debug_write('Performing starter stratergy {} of your custom algo strategy'.format(game_state.turn_number))

        gamelib.debug_write('Previous stationary units - pre call: ' + str(self.last_round_stationary_units))

        if game_state.turn_number == 0:
            # Build defences
            self.build_intial_defences(game_state)
            # Create attack
            self.play_inital_attack(game_state)
        else:
            # Build defences - first rebuild what we lost and then add to what we have
            self.queue_rebuild_lost_defenses(game_state)
            gamelib.debug_write('Current Queue: ' + str(self.structure_queue[0]))

            self.build_new_defences(game_state)

            # Create attack.
            if self.should_thunder_strike(game_state) and self.play_thunder == -1:
                self.prepare_thunder_attack(game_state)
                self.play_thunder = 0
            elif self.play_thunder == 0:
                self.play_thunder_strike(game_state)
                self.play_thunder = 1
            elif self.play_thunder == 1:
                self.rebuild_after_thunder_strike(game_state)
                self.play_thunder = -1
            else:
                # Pick standard attack.
                self.play_standard_attack(game_state)

        # Last call of the round which is used to figure out what was destroyed.
        self.last_round_stationary_units = self.get_current_stationary_units(game_state)
        gamelib.debug_write('Previous stationary units - post call: ' + str(self.last_round_stationary_units))

        

    def build_intial_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Get my own points.
        gamelib.debug_write('Queue size: {}'.format(len(self.structure_queue)))

        # Place the inital defenses.
        while(len(self.structure_queue) > 0 and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            gamelib.debug_write('Number of SP: {}'.format(game_state.get_resource(resource_type=SP, player_index=0)))
            placement = self.structure_queue.popleft()
            number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(placement.name, placement.x, placement.y, number_placed))

        # Add to the queue the things we want to upgrade and build next.
        turrents_to_add = [[21, 11], [20, 9], [1, 13]]
        for tur in turrents_to_add:
            self.structure_queue.append(building(name=TURRET, x=tur[0], y=tur[1]))
        
        supports_to_add = [[13, 2]]
        for supp in supports_to_add:
            self.structure_queue.append(building(name=SUPPORT, x=supp[0], y=supp[1]))


        # Upgrades to do.
        # RHS turrets
        # RHS walls
        # LHS turrets
        # Supports.
        upgrade_locations = [[21, 11], [20, 9], [22, 12], [23, 12],  
                             [25, 13], [26, 13], [27, 13], [24, 12],           
                             [22, 11], [1, 12], [2, 12], [1, 13], 
                             [13, 2], [14, 2]]
        
        for up in upgrade_locations:
            self.structure_queue.append(building(name="upgrade", x= up[0], y=up[1]))

        # Extra turrents on the RHS and LHS.
        extra_def = [[18, 10], [19, 10], [19, 9], [3, 11]]
        for new_def in extra_def:
            self.structure_queue.append(building(name=TURRET, x=new_def[0], y=new_def[1]))
        
        # Extra walls on RHS to draw damage.
        extra_walls = [[22, 13], [23, 13], [20, 12], [21, 12], [24, 23]]
        for new_wall in extra_walls:
            self.structure_queue.append(building(name=WALL, x=new_wall[0], y=new_wall[1]))
        
        # Update extra defenses
        for new_def in extra_def:
            self.structure_queue.append(building(name="upgrade", x=new_def[0], y=new_def[1]))

        # Add more supports now
        extra_supp = [[17, 6], [16, 5], [15, 4], [14, 4]]
        for new_supp in extra_supp:
            self.structure_queue.append(building(name=SUPPORT, x=new_supp[0], y=new_supp[1]))
        
        # Update extra support
        for new_def in extra_def + extra_walls:
            self.structure_queue.append(building(name="upgrade", x=new_def[0], y=new_def[1]))

        # Then just flood with defenses
        flood_def = [[19, 13], [20, 13], [21, 13], [17, 12], [19, 12], [17, 11], [17, 10]]
        for f_def in flood_def:
            self.structure_queue.append(building(name=TURRET, x=f_def[0], y=f_def[1]))

        # Update extra defenses
        for f_def in flood_def:
            self.structure_queue.append(building(name="upgrade", x=f_def[0], y=f_def[1]))



    def build_new_defences(self, game_state):

        ''' 
        This should take way is on the queue and build with it / upgrade it
        '''
        gamelib.debug_write('Queue size: {}'.format(len(self.structure_queue)))

        # Place the inital defenses.
        number_placed = 1
        # Check whether we have enough to place the next item (lazy eval so fine).
        # This should stop things being popped off the queue and not being built.
        while(number_placed > 0 and len(self.structure_queue) > 0 and game_state.get_resource(resource_type=SP, player_index=0) > 0):
            gamelib.debug_write('Number of SP: {}'.format(game_state.get_resource(resource_type=SP, player_index=0)))
            placement = self.structure_queue.popleft()
            # Need to careful here whether we decide to upgrade or build a new defence.
            if(placement.name == 'upgrade'):
                number_placed = game_state.attempt_upgrade([placement.x, placement.y])
            else: 
                number_placed = game_state.attempt_spawn(placement.name, [placement.x, placement.y])
            
            if number_placed == 0:
                # Need to add back into the queue.
                self.structure_queue.appendleft(placement)

            gamelib.debug_write('Attempting to spawn {} at location ({}, {}). Number placed: {}'.format(placement.name, placement.x, placement.y, number_placed))


    def queue_rebuild_lost_defenses(self, game_state):

        '''
        Identify the buildings which were lost in the previous round and then place onto the queue
        and attempt to upgrade these
        '''

        rebuild_list = self.find_destroyed_buildings(game_state)

        # DO NOT REPLACE LIST: Thunderstrike.
        non_replacements = {(WALL, 25, 13), (WALL, 26, 13), (WALL, 27, 13), (WALL, 21, 10)}
        rebuild_list = rebuild_list - non_replacements
        gamelib.debug_write('Thunderstike, saving wall: ' + str(rebuild_list - non_replacements))
        gamelib.debug_write('Rebuild list' + str(rebuild_list))
            
        # Use this as a heuristic to upgrade these buildings are they are likely to be attacked again. 
        # When pushing in from the left need to ensure we do in in backwards order.
        for item in rebuild_list:
            self.structure_queue.appendleft(building(name='upgrade', x=item[1], y=item[2]))

        for item in rebuild_list:
            self.structure_queue.appendleft(building(name=item[0], x=item[1], y=item[2]))


    def play_inital_attack(self, game_state):

        # Place a double interceptor halfway up the right hand side in order to tackle anything inbound.
        deploy_location = [20,6]
        game_state.attempt_spawn(INTERCEPTOR, deploy_location, 2)



    def play_standard_attack(self, game_state):

        '''
        Just a normal attack using 2 scouts, more to see if we can do damage and expliot weekness
        '''
        if(game_state.get_resource(resource_type=MP, player_index=0) > 8 and game_state.turn_number % 4 == 0):
            game_state.attempt_spawn(DEMOLISHER, [[11, 2]], 1)



    def should_thunder_strike(self, game_state):
        # TODO - Add logic with number of MP.

        return (game_state.get_resource(resource_type=MP, player_index=0) > 20 and game_state.get_resource(resource_type=SP, player_index=0) >= 5)


    def prepare_thunder_attack(self, game_state):
        # Remove the walls.
        walls_to_remove = [25, 13], [26, 13], [27, 13]
        game_state.attempt_remove(walls_to_remove)


    def rebuild_after_thunder_strike(self, game_state):

        # Replace the front 3 walls. 
        walls_to_replace = [25, 13], [26, 13], [27, 13]
        game_state.attempt_spawn(WALL, walls_to_replace)
        game_state.attempt_upgrade(walls_to_replace)

        # Remove the blocking piece.
        # game_state.attempt_remove([[21, 10]])


    def play_thunder_strike(self, game_state):

        '''
        This is the play in which we remove the blocking tiles and then charge with scouts / demolisher
        '''

        # TODO - Need to write this so it's varible.

        # Block of the path so we head straight for the RHS.
        game_state.attempt_spawn(WALL, locations=[[21, 10]])

        # Place an demolisher up the RHS to start.
        # game_state.attempt_spawn(DEMOLISHER, locations=[[17, 3]], num=2)

        # Scouts, use as many as we can afford.
        game_state.attempt_spawn(SCOUT, locations=[12, 1], num=5)
        game_state.attempt_spawn(SCOUT, locations=[11, 2], num=game_state.get_resource(resource_type=MP, player_index=0) - 5)

        # TODO - In future we should optimise this for weather we will get blocked, and how much we can risk etc.

        # Interceptor to clean up afterwards.
        # game_state.attempt_spawn(INTERCEPTOR, locations=[[14, 0]], num=2)

        game_state.attempt_remove([[21, 10]])
            
    # def build_reactive_defense(self, game_state):
    #     """
    #     This function builds reactive defenses based on where the enemy scored on us from.
    #     We can track where the opponent scored by looking at events in action frames 
    #     as shown in the on_action_frame function
    #     """
    #     for location in self.scored_on_locations:
    #         # Build turret one space above so that it doesn't block our own edge spawn locations
    #         build_location = [location[0], location[1]+1]
    #         game_state.attempt_spawn(TURRET, build_location)

    

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

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
                        

    def find_destroyed_buildings(self, game_state):
        ''' 
        returns locations and what was destroyed in the form [type, [location_x, location_y]]
        Used to figure out what was lost between this round and the last round.
        '''
        current_stationary_units = self.get_current_stationary_units(game_state)
        gamelib.debug_write('Current Station Units: ' + str(current_stationary_units))
        gamelib.debug_write('Last rounds stationary Units: ' + str(self.last_round_stationary_units))
        gamelib.debug_write('Diffence: ' + str(set(self.last_round_stationary_units) - set(current_stationary_units)))
        return self.last_round_stationary_units - current_stationary_units


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
