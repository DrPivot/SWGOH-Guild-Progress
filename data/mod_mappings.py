"""
Mod Set and Primary Stat Mappings for SWGOH
Extracted from statModSet.json and HU data analysis
"""

# Mod Set Mappings: {set_id: (name, set_count)}
# set_count: number of mods required for set bonus (2 or 4)
# Uses unitStatId from statModSet.json (not the set "id"!)
MOD_SETS = {
    '55': ('Health', 2),          # Set ID 1 → unitStatId 55 (Health %)
    '48': ('Offense', 4),         # Set ID 2 → unitStatId 48 (Offense %)
    '49': ('Defense', 2),         # Set ID 3 → unitStatId 49 (Defense %)
    '57': ('Speed', 4),           # Set ID 4 → unitStatId 57 (Speed) - MOST COMMON!
    '53': ('Crit Chance', 2),     # Set ID 5 → unitStatId 53 (Crit Chance)
    '16': ('Crit Damage', 4),     # Set ID 6 → unitStatId 16 (Crit Damage)
    '17': ('Potency', 2),         # Set ID 7 → unitStatId 17 (Potency/Accuracy)
    '18': ('Tenacity', 2),        # Set ID 8 → unitStatId 18 (Tenacity/Resistance)
}

# Primary Stat Mappings: {stat_id: name}
# Verified with actual game data from DrPivot's roster
PRIMARY_STATS = {
    '0': 'Empty/Unmoded',
    '5': 'Speed',              
    '16': 'Crit Damage',       
    '17': 'Potency',           
    '18': 'Tenacity',          
    '48': 'Offense',         
    '49': 'Defense',         
    '52': 'Accuracy',        
    '53': 'Crit Chance',     
    '54': 'Crit Avoidance',  
    '55': 'Health',          
    '56': 'Protection',
}

# Slot Names for display
SLOT_NAMES = {
    'PrimaryArrow': 'Arrow',
    'PrimaryTriangle': 'Triangle',
    'PrimaryCircle': 'Circle',
    'PrimaryCross': 'Cross'
}

def get_mod_set_name(set_id):
    """Returns mod set name and count, or Unknown if not found."""
    set_id_str = str(set_id)
    if set_id_str in MOD_SETS:
        return MOD_SETS[set_id_str]
    return (f'Unknown-{set_id}', 0)

def get_primary_stat_name(stat_id):
    """Returns primary stat name, or Unknown if not found."""
    stat_id_str = str(stat_id)
    if stat_id_str in PRIMARY_STATS:
        return PRIMARY_STATS[stat_id_str]
    return f'Unknown-{stat_id}'
