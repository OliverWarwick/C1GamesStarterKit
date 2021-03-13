import gamelib
import random
import math
import warnings
from sys import maxsize
import json
from gamelib.unit import GameUnit
import copy
from collections import deque, namedtuple
import time

class Simulator:

    def __init__(self, game_state, config):
        self.original_game_state = game_state
        self.simulated_game_state = copy.deepcopy(game_state)
        self.config = config

        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP

        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]

        self.valid_board_coords = [[0, 13], [0, 14], [1, 12], [1, 13], [1, 14], [1, 15], [2, 11], [2, 12], [2, 13], [2, 14], [2, 15], [2, 16], [3, 10], [3, 11], [3, 12], [3, 13], [3, 14], [3, 15], [3, 16], [3, 17], [4, 9], [4, 10], [4, 11], [4, 12], [4, 13], [4, 14], [4, 15], [4, 16], [4, 17], [4, 18], [5, 8], [5, 9], [5, 10], [5, 11], [5, 12], [5, 13], [5, 14], [5, 15], [5, 16], [5, 17], [5, 18], [5, 19], [6, 7], [6, 8], [6, 9], [6, 10], [6, 11], [6, 12], [6, 13], [6, 14], [6, 15], [6, 16], [6, 17], [6, 18], [6, 19], [6, 20], [7, 6], [7, 7], [7, 8], [7, 9], [7, 10], [7, 11], [7, 12], [7, 13], [7, 14], [7, 15], [7, 16], [7, 17], [7, 18], [7, 19], [7, 20], [7, 21], [8, 5], [8, 6], [8, 7], [8, 8], [8, 9], [8, 10], [8, 11], [8, 12], [8, 13], [8, 14], [8, 15], [8, 16], [8, 17], [8, 18], [8, 19], [8, 20], [8, 21], [8, 22], [9, 4], [9, 5], [9, 6], [9, 7], [9, 8], [9, 9], [9, 10], [9, 11], [9, 12], [9, 13], [9, 14], [9, 15], [9, 16], [9, 17], [9, 18], [9, 19], [9, 20], [9, 21], [9, 22], [9, 23], [10, 3], [10, 4], [10, 5], [10, 6], [10, 7], [10, 8], [10, 9], [10, 10], [10, 11], [10, 12], [10, 13], [10, 14], [10, 15], [10, 16], [10, 17], [10, 18], [10, 19], [10, 20], [10, 21], [10, 22], [10, 23], [10, 24], [11, 2], [11, 3], [11, 4], [11, 5], [11, 6], [11, 7], [11, 8], [11, 9], [11, 10], [11, 11], [11, 12], [11, 13], [11, 14], [11, 15], [11, 16], [11, 17], [11, 18], [11, 19], [11, 20], [11, 21], [11, 22], [11, 23], [11, 24], [11, 25], [12, 1], [12, 2], [12, 3], [12, 4], [12, 5], [12, 6], [12, 7], [12, 8], [12, 9], [12, 10], [12, 11], [12, 12], [12, 13], [12, 14], [12, 15], [12, 16], [12, 17], [12, 18], [12, 19], [12, 20], [12, 21], [12, 22], [12, 23], [12, 24], [12, 25], [12, 26], [13, 0], [13, 1], [13, 2], [13, 3], [13, 4], [13, 5], [13, 6], [13, 7], [13, 8], [13, 9], [13, 10], [13, 11], [13, 12], [13, 13], [13, 14], [13, 15], [13, 16], [13, 17], [13, 18], [13, 19], [13, 20], [13, 21], [13, 22], [13, 23], [13, 24], [13, 25], [13, 26], [13, 27], [14, 0], [14, 1], [14, 2], [14, 3], [14, 4], [14, 5], [14, 6], [14, 7], [14, 8], [14, 9], [14, 10], [14, 11], [14, 12], [14, 13], [14, 14], [14, 15], [14, 16], [14, 17], [14, 18], [14, 19], [14, 20], [14, 21], [14, 22], [14, 23], [14, 24], [14, 25], [14, 26], [14, 27], [15, 1], [15, 2], [15, 3], [15, 4], [15, 5], [15, 6], [15, 7], [15, 8], [15, 9], [15, 10], [15, 11], [15, 12], [15, 13], [15, 14], [15, 15], [15, 16], [15, 17], [15, 18], [15, 19], [15, 20], [15, 21], [15, 22], [15, 23], [15, 24], [15, 25], [15, 26], [16, 2], [16, 3], [16, 4], [16, 5], [16, 6], [16, 7], [16, 8], [16, 9], [16, 10], [16, 11], [16, 12], [16, 13], [16, 14], [16, 15], [16, 16], [16, 17], [16, 18], [16, 19], [16, 20], [16, 21], [16, 22], [16, 23], [16, 24], [16, 25], [17, 3], [17, 4], [17, 5], [17, 6], [17, 7], [17, 8], [17, 9], [17, 10], [17, 11], [17, 12], [17, 13], [17, 14], [17, 15], [17, 16], [17, 17], [17, 18], [17, 19], [17, 20], [17, 21], [17, 22], [17, 23], [17, 24], [18, 4], [18, 5], [18, 6], [18, 7], [18, 8], [18, 9], [18, 10], [18, 11], [18, 12], [18, 13], [18, 14], [18, 15], [18, 16], [18, 17], [18, 18], [18, 19], [18, 20], [18, 21], [18, 22], [18, 23], [19, 5], [19, 6], [19, 7], [19, 8], [19, 9], [19, 10], [19, 11], [19, 12], [19, 13], [19, 14], [19, 15], [19, 16], [19, 17], [19, 18], [19, 19], [19, 20], [19, 21], [19, 22], [20, 6], [20, 7], [20, 8], [20, 9], [20, 10], [20, 11], [20, 12], [20, 13], [20, 14], [20, 15], [20, 16], [20, 17], [20, 18], [20, 19], [20, 20], [20, 21], [21, 7], [21, 8], [21, 9], [21, 10], [21, 11], [21, 12], [21, 13], [21, 14], [21, 15], [21, 16], [21, 17], [21, 18], [21, 19], [21, 20], [22, 8], [22, 9], [22, 10], [22, 11], [22, 12], [22, 13], [22, 14], [22, 15], [22, 16], [22, 17], [22, 18], [22, 19], [23, 9], [23, 10], [23, 11], [23, 12], [23, 13], [23, 14], [23, 15], [23, 16], [23, 17], [23, 18], [24, 10], [24, 11], [24, 12], [24, 13], [24, 14], [24, 15], [24, 16], [24, 17], [25, 11], [25, 12], [25, 13], [25, 14], [25, 15], [25, 16], [26, 12], [26, 13], [26, 14], [26, 15], [27, 13], [27, 14]]

        self.start_time = None

        # DAVID / HENRY LOOK

        self.health_weighting = 1
        self.turret_weighting = 0.3
        self.support_weighting = 0.2
        self.wall_weighting = 0.1

        self.verbose = False
        self.timing_verbose = False

       


    def reset(self):

        self.simulated_game_state = copy.deepcopy(self.original_game_state)


    def roll_out_one_turn(self, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):

        ''' 
        This will roll out a play give a set of placements of our attackers, our defenders, oppo attackers, oppo defenders
        return:
            (float, float): my_health, enemy_health
        '''

        # Can use the can_spawn function.
        # Need to ensure that we create new units to place in the game map.

        # Create a copy of the game state.
        if self.verbose: gamelib.debug_write("Beginning roll out")

        if self.verbose: gamelib.debug_write("Before start of sim")
        if self.verbose: self.print_map(self.simulated_game_state)
        self.start_time = time.time()
        
        # Add the units.
        self.add_proposed_units_to_map(self.simulated_game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list)
        if self.verbose: gamelib.debug_write("Units on the map")
        if self.verbose: self.print_map(self.simulated_game_state)

        # Set up inital coords and movement paths.
        self.set_movement_paths(self.simulated_game_state)

        # Simulate turn
        self.simulate_one_turn(self.simulated_game_state)

        if self.verbose: gamelib.debug_write("Finished roll out")
        if self.verbose: self.print_map(self.simulated_game_state)

        if self.verbose: gamelib.debug_write("Finished roll out")
        if self.verbose: self.print_map(self.simulated_game_state)

        # Here we return important data.
        self.simulated_game_state.get_game_state_metrics()
        if self.verbose: gamelib.debug_write("My Health: {}  Enemy Health: {} ".format(self.simulated_game_state.my_health, self.simulated_game_state.enemy_health))

        final_score = self.eval_updated_game_state(self.simulated_game_state.game_state_info)
        if self.verbose: gamelib.debug_write("Final Score: {}".format(final_score))
        return final_score



    def eval_updated_game_state(self, game_state_info):
        ''' 
        Using the current weights, evaluate the ending game state.
        '''
        return self.health_weighting * (game_state_info['my_health'] - game_state_info['enemy_health']) + \
        self.turret_weighting * (game_state_info['my_turret_count'] - game_state_info['oppo_turret_count']) + \
        self.support_weighting * (game_state_info['my_support_count'] - game_state_info['oppo_support_count']) + \
        self.wall_weighting * (game_state_info['my_wall_count'] - game_state_info['oppo_wall_count'])


    def add_proposed_units_to_map(self, game_state, our_attacker_list, oppo_attacker_list, our_building_list, oppo_building_list):

        # Pass to the helper function.
        for att in our_attacker_list:
            self.add_single_location_of_units(game_state, 'attacker', att, player_index=0)
        for att in oppo_attacker_list:
            self.add_single_location_of_units(game_state, 'attacker', att, player_index=1)
        for defence in our_building_list:
            self.add_single_location_of_units(game_state, 'building', defence, player_index=0)
        for defence in oppo_building_list:
            self.add_single_location_of_units(game_state, 'building', defence, player_index=1)
        
    
    def add_single_location_of_units(self, game_state, style, element, player_index):
        ''' 
        style whether attack or stationary, element is just the tuple and player index 0 / 1 as above. 
        This should be a valid allocation based on what the oppo has.
        '''
        if style == 'attacker':
            # This will be an 
            # attacker = namedtuple('Attacker', ['name', 'x', 'y', 'num'])
            for _ in range(0, element.num):
                # Can only add one at a time.
                if self.verbose: gamelib.debug_write("Doing add of attacker {} to ({}, {})".format(element.name, element.x, element.y))
                game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
        else:
            # building = namedtuple('Building', ['name', 'x', 'y'])
            if element.name != 'upgrade':
                if self.verbose: gamelib.debug_write("Doing add of defender {} to ({}, {})".format(element.name, element.x, element.y))
                game_state.game_map.add_unit(unit_type=element.name, location=[element.x, element.y], player_index=player_index)
            else:
                if self.verbose: gamelib.debug_write("Doing upgrade at ({}, {})".format(element.x, element.y))
                if self.verbose: gamelib.debug_write("Current Unit: {}".format(game_state.game_map[element.x, element.y]))
                game_state.game_map[element.x, element.y][0].upgrade()


        

    def set_movement_paths(self, game_state):

        # After adding the units, run across the game map and set the path for each of units.
        # The inital coords will be used for mapping in the future.
        for loc in self.valid_board_coords:
            for unit in game_state.game_map[loc]:
                if not unit.stationary:
                    # Get the initial path.
                    path = game_state.find_path_to_edge(loc)
                    if path == None:
                        path = [loc]
                    # This is a mobile unit so set the path, initial_x, and initial_y
                    unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])
                else:
                    path = None
                    unit.set_extra_conditions(path=path, x=loc[0], y=loc[1])



    def simulate_one_turn(self, game_state):
        ''' 
        Pre Condition: Valid board configuation and that "RESTORE" has already happened and "DEPLOY" phase has been simed.
        This rolls out one play based on a game state which is in it's final modifed state before the first action frame
        return:
            GameState: with the game state at the end of the turn from our perspective.
        '''
        not_done = True
        buildings_destroyed = False
        current_frame_num = 0
        if self.verbose: gamelib.debug_write("Simulating one play forward.")
        while(current_frame_num < 1000 and not_done):
            current_frame_num, not_done, buildings_destroyed = self.simulate_one_action_frame(game_state, current_frame_num, buildings_destroyed)
            if self.verbose: self.print_map(game_state=game_state)

        if self.verbose: gamelib.debug_write("Time elpased to simulator 1 turn: {}".format(time.time() - self.start_time))



    def simulate_one_action_frame(self, game_state, frame_num, buildings_destroyed):
        ''' 
        Pre Condition: Valid board configuation.
        Roll out one action frame using the game logic and return this
        return: 
            GameState: after movements
        OW changint the targetting algo.
        '''

        # To hold the new values 
        updated_game_map = gamelib.GameMap(self.config)

        if self.verbose: gamelib.debug_write("Frame Number: {}".format(frame_num))
        if self.verbose: gamelib.debug_write("Building Destoryed: {}".format(buildings_destroyed))

        for loc in self.valid_board_coords:
                for unit in game_state.game_map[loc]:
                    if not unit.stationary: 
                        unit.has_been_shielded = False
        
        # Add any health bonuses which I think should be done before. (STAGE 0.)
        for loc in self.valid_board_coords:
            if game_state.game_map.in_arena_bounds(loc) and len(game_state.game_map[loc]) == 1 and game_state.game_map[loc][0].unit_type == SUPPORT:
                # Get the locations within range:
                supported_locations = game_state.game_map.get_locations_in_range(loc, game_state.game_map[loc][0].shieldRange)
                for sup_loc in supported_locations:
                    for unit in game_state.game_map[sup_loc]:
                        if not unit.stationary and not unit.has_been_shielded:
                            unit.health += game_state.game_map[loc][0].shieldPerUnit
                            unit.has_been_shielded = True
                            if self.verbose: gamelib.debug_write("Adding health to unit at location ({}, {})".format(sup_loc[0], sup_loc[1]))

        if self.verbose: gamelib.debug_write("End of adding health bonuses")
    
        # All units take a step if it is their turn. (STAGE 1).
        movement = False
        troops_alive = False
        self_destruct_list = []         # List[x, y] locations for self destruct. Have to be done together as a location.
        for loc in self.valid_board_coords:
            # We have at least one unit here, so run through them, and find the target.
            for unit in game_state.game_map[loc]:

                # If unit is stationary, then copy onto the new map. Otherwise apply the update logic.
                if unit.stationary:
                    updated_game_map.add_existing_unit(unit, location=loc)
                else:
                    troops_alive = True
                    # Remove the unit from the current location and add to the path.
                    if not buildings_destroyed:
                        path = unit.current_path
                        if self.verbose: gamelib.debug_write("Unit at location: ({}, {}) no need to repath.".format(loc[0], loc[1]))
                    else:
                        # Need to repath the path now.
                        unit.current_path = game_state.find_path_based_on_initial(unit)
                        path = unit.current_path
                        if self.verbose: gamelib.debug_write("Unit at location: ({}, {}) repathing.".format(loc[0], loc[1]))

                    # Should only move when it is there multiple
                    if self.verbose: gamelib.debug_write("Unit at location: ({}, {}). Path to end: {}".format(loc[0], loc[1], path))
                    if self.verbose: gamelib.debug_write("Unit Location: ({}, {}). FrameNum: {}. Speed: {}".format(loc[0], loc[1],frame_num, unit.speed))
                    if frame_num == 0 or int(frame_num) % int(1.0 / unit.speed) == 0:
                        
                        if loc == path[-1]:
                            if self.verbose: gamelib.debug_write("Unit at location: ({}, {}) is at the end of the path.".format(loc[0],loc[1]))
                            # We are at the end of the path. Either we are at an edge which means we can remove health, or we are in the middle of the board which means we need to self-destruct.
                            if unit.player_index == 0 and loc in game_state.game_map.get_edge_locations(game_state.game_map.TOP_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.TOP_RIGHT):
                                # Score on enemy.
                                # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
                                game_state.enemy_health -= 1
                                if self.verbose: gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
                            elif unit.player_index == 1 and loc in game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT):
                                # Score on us.
                                # game_state.game_map.remove_one_unit(location=[loc[0], loc[1]], unit=unit)
                                game_state.my_health -= 1
                                if self.verbose: gamelib.debug_write("Removing points from enemy because of unit at location ({}, {})".format(loc[0], loc[1]))
                            else:
                                # This is now a self destruct so will need handling.
                                # TODO - These units should be allowed to attack first.
                                if self.verbose: gamelib.debug_write("Calling the self destruct logic for location: ({}, {})".format(loc[0], loc[1]))
                                successfully_updated = updated_game_map.add_existing_unit(unit, location=loc)
                                self_destruct_list.append(loc)
                        else:
                            # Find the next location in the path
                            for index, path_loc in enumerate(path):
                                # gamelib.debug_write('Searching for path element matching. Currently {}, looking for {}'.format(path_loc, loc))
                                if path_loc == loc:
                                    break

                            if index == len(path) - 1:
                                # This signals an error that we could not find a match so throw an error
                                gamelib.debug_write("BIG PROBLMEMMMMMMMMO. Could not find current location in the path which is very bad.")
                            else:
                                # Should be able to get next term. No need to check i+1 is valid because above loop would have caught path[-1] == loc.
                                # successfully_removed = updated_game_map.remove_one_unit(location=loc, unit=unit)
                                unit.x, unit.y = path[index+1]
                                # Add to the updated game map.
                                successfully_updated = updated_game_map.add_existing_unit(unit, location=path[index+1])
                                if self.verbose: gamelib.debug_write("Updated: {}".format(successfully_updated))
                                
                                # SHOULD WE REMOVE FROM OUR GAME MAP? 
                                # game_state.game_map.move_unit(unit=unit, location=path[index+1])
                                movement = True
                                if self.verbose: gamelib.debug_write("Moved Unit form ({}, {}) old map to ({}, {}) new map".format(loc[0], loc[1], unit.x, unit.y))
                    else:
                        # None moving piece this turn so just copy over.
                        updated_game_map.add_existing_unit(unit, location=loc)

        # We now have an updated game_map, so we can use this to perform the attacks.
        # Set the new game_map to our game_state.                
        game_state.game_map = updated_game_map
        buildings_destroyed = False     

        # For units in the self-destruct list we can call the logic.
        for loc in self_destruct_list:
            for unit in game_state.game_map[loc]:
                buildings_destroyed = self.self_destruct_logic(game_state, unit, buildings_destroyed)
                # Remove this unit from the game_map.
                game_state.game_map.remove_one_unit(loc, unit)

        
        # Then look at all of the attacks.
        # All units attack (STAGE 2).
        for loc in self.valid_board_coords:
            # We have at least one unit here, so run through them, and find the target.
            for unit in game_state.game_map[loc]:
                # Find the target
                if self.verbose: gamelib.debug_write("Unit currently attacking: {}".format(unit))
                target_unit = game_state.get_target(unit)
                if self.verbose: gamelib.debug_write("Target : {}".format(target_unit))
                if target_unit is not None:
                    # Remove health from these units picking whether to use the damage to stationary and moving units
                    # IMPORTANT: NEED TO REFER TO THESE USING THE UNITS ARE GAME_MAP CAN HAVE MORE THAN ONE ELEMENT IN THE LIST AT EACH LOCATION 
                    if(target_unit.stationary):
                        target_unit.health -= unit.damage_f
                        if self.verbose: gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_f))
                    else:
                        target_unit.health -= unit.damage_i
                        if self.verbose: gamelib.debug_write("Unit at location ({}, {}) firing at target ({}, {}) doing damage {}".format(loc[0], loc[1], target_unit.x, target_unit.y, unit.damage_i))
                    
                    # Remove if health has fallen below zero. (STAGE 3). (techincally in stage 3 but I think it works here)
                    if target_unit.health <= 0:
                        # Remove from the list.
                        # TODO - Check this works, unsure it deffo will.
                        game_state.game_map.remove_one_unit(location=[target_unit.x, target_unit.y], unit=target_unit)
                        if self.verbose: gamelib.debug_write("Removing unit at location ({}, {})".format(loc[0], loc[1]))
                        if target_unit.stationary:
                            buildings_destroyed = True      # This is to trigger a repathing.


        if self.verbose: gamelib.debug_write("Finished rolling forward one step.")
        if self.verbose: gamelib.debug_write("Passing back values. Movement: {}, BuildingDest: {}".format(movement, buildings_destroyed))
        # Return with next frame and whether done or not.
        return (frame_num + 1, movement or troops_alive, buildings_destroyed)


    def self_destruct_logic(self, game_state, unit, buildings_destroyed):
        '''
        Args: 
            unit: GameUnit which is self-destructing.
        '''
        # First need to check that the unit has moved at least 5 squares.
        if(abs(unit.x - unit.initial_x) + abs(unit.y - unit.initial_y) >= 5):
            damage = unit.max_health * 1.5
            damage_locations = game_state.game_map.get_locations_in_range(location=[unit.x, unit.y], radius=1.5)
            for loc in damage_locations:
                if loc != [unit.x, unit.y]:
                    for targeted_unit in game_state.game_map[loc]:
                        targeted_unit.health -= damage
                        if targeted_unit.health <= 0:
                            game_state.game_map.remove_one_unit([targeted_unit.x, targeted_unit.y], targeted_unit)
                            buildings_destroyed = True
        return buildings_destroyed
                            
       

            
    '''
    Within GameMap: 
        distance_between_locations(loc1, loc2)
        get_location_in_range(loc, radius)

    Within GameState:
        get_target(attacking unit): GameUnit
        get_attackers(location, player_index): List[GameUnit]
        get_target_edge(start_location)
        find_path_to_edge(start_location, target_edge) : List[[x, y]]

    '''



    def print_map(self, game_state):
        gamelib.debug_write('Map:\n')
        for i in range(0,28):
            row_str = "|" 
            for j in range(0,28):
                if game_state.game_map.in_arena_bounds([i,j]):
                    if len(game_state.game_map[i,j]) > 0:
                        row_str += (str(game_state.game_map[i,j][0].player_index) + str(game_state.game_map[i,j][0].unit_type) + " " + str(int(game_state.game_map[i,j][0].health)) + (5-len(str(game_state.game_map[i,j][0].unit_type) + str(game_state.game_map[i,j][0].health))) * " ")
                        # gamelib.debug_write(type(new_state.game_map[i,j][0]))
                    else: 
                        row_str += "       "
                else:
                    row_str += "-------"
            gamelib.debug_write(row_str)