import discord
GUILD_ID = 864441968776052747
GUILD = discord.Object(id=GUILD_ID)


####################
# PEOPLE
####################

EVERYONE = 864441968776052747


####################
# BTR CHANNELS
####################

# Doormat
WELCOME = 865515335867301908

# Command
STAFF_CHAT = 864442610613485590
MODERATION_LOG = 866938361628852224
BOT = 865511340911493131

# Scheduling
SCHEDULE = 864487380366000178
WORKSHOP_INTEREST = 893876429098475581

# Community
GENERAL = 864441969286578178
ARMA_DISCUSSION = 864487446611623986
COMBAT_FOOTAGE = 895606965525442600
PROPAGANDA = 968823323993726996

# Bot Stuff
BOT_SPAM = 976953703653314582

# Operations
COMMAND = 864487652124131349  # Voice
DEPLOYED = 864487710545674320  # Voice


####################
# BTR RANKS
####################

PROSPECT = 977544142341165106  # Received upon joining
VERIFIED = 864443957625618463  # After interview
ASSOCIATE = 864443914668474399  # Newcomer workshop
CONTRACTOR = 864443893852667932  # Good rifleman
OPERATOR = 864443872003620874  # Good TL
TECHNICIAN = 864443849342189577  # 1+ SMEs
SPECIALIST = 864443819571019776  # Good actual
ADVISOR = 864443725248462848  # 1+ SMEs + Good actual

PROMOTIONS = {
    PROSPECT: VERIFIED,
    VERIFIED: ASSOCIATE,
    ASSOCIATE: CONTRACTOR,
    CONTRACTOR: OPERATOR,
    OPERATOR: SPECIALIST,
    SPECIALIST: ADVISOR,
    TECHNICIAN: ADVISOR
}
DEMOTIONS = {
    VERIFIED: PROSPECT,
    ASSOCIATE: VERIFIED,
    CONTRACTOR: ASSOCIATE,
    OPERATOR: CONTRACTOR,
    TECHNICIAN: CONTRACTOR,
    SPECIALIST: OPERATOR,
    ADVISOR: TECHNICIAN
}


####################
# BTR SPECIAL ROLES
####################

UNIT_STAFF = 864443672032706560

SERVER_HAMSTER = 977542488661323846
CURATOR = 977543359432380456
MISSION_BUILDER = 977543401895522377
ZEUS = 977543532904583199


####################
# BTR SMES
####################

SME_RW_PILOT = 864443977658925107
SME_FW_PILOT = 970078666862235698
SME_JTAC = 970078704527114270
SME_MEDIC = 970078742552645714
SME_HEAVY_WEAPONS = 970078799200935956
SME_MARKSMAN = 970078835984973834
SME_BREACHER = 970078881073741835
SME_MECHANISED = 970078944277717053
SME_RPV_SO = 970078977542725632
SME_ARTILLERY = 970079008903532644
SME_MENTOR = 977542996318887966

SME_ROLES = (SME_RW_PILOT, SME_FW_PILOT, SME_JTAC, SME_MEDIC, SME_HEAVY_WEAPONS, SME_MARKSMAN, SME_BREACHER, SME_MECHANISED, SME_RPV_SO, SME_ARTILLERY, SME_MENTOR)


####################
# BTR EMOJIS
####################

GREEN = 874935884192043009
RED = 874935884208820224
YELLOW = 874935884187836447
BLUE = 877938186238701598
