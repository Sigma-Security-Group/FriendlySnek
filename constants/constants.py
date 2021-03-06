import discord
GUILD_ID = 288446755219963914
GUILD = discord.Object(id=GUILD_ID)

TIME_ZONES = {
    "UTC": "UTC",
    "British Time (London)": "Europe/London",
    "Central European Time (Brussels)": "Europe/Brussels",
    "Eastern European Time (Sofia)": "Europe/Sofia",
    "Pacific American Time (LA)": "America/Los_Angeles",
    "Eastern American Time (NY)": "America/New_York",
    "Japanese Time (Tokyo)": "Asia/Tokyo",
    "Australian Western Time (Perth)": "Australia/Perth",
    "Australian Central Western Time (Eucla)": "Australia/Eucla",
    "Australian Central Time (Adelaide)": "Australia/Adelaide",
    "Australian Eastern Time (Sydney)": "Australia/Sydney",
}


####################
# PEOPLE
####################

ADRIAN = 216027379506741249
FROGGI = 229212817448894464
KYANO = 253576571183562752
DEVELOPERS = (ADRIAN, FROGGI)

EVERYONE = 288446755219963914


####################
# BOTS
####################

CARL_BOT = 235148962103951360
DYNO = 155149108183695360
TICKET_TOOL = 557628352828014614

FRIENDLY_SNEK = 864039882397974538
FRIENDLY_SNEK_DEV = 865107689113387018
FRIENDLY_SNEK_DEV_FROGGI = 942214717945036820
FRIENDLY_SNEK_DEV_KLOS = 852279506537807932

FRIENDLY_SNEKS = (FRIENDLY_SNEK, FRIENDLY_SNEK_DEV, FRIENDLY_SNEK_DEV_FROGGI, FRIENDLY_SNEK_DEV_KLOS)


####################
# SSG CHANNELS
####################

# Doormat
WELCOME = 743624201692250183

# Command
STAFF_CHAT = 740368938239524995
MODERATION_LOG = 730174175897059328
BOT = 702231226618216630

# Scheduling
SCHEDULE = 852299426936782898
WORKSHOP_INTEREST = 895582645210206208

# Community
GENERAL = 740365307276689438
ARMA_DISCUSSION = 827147720284045322
COMBAT_FOOTAGE = 655474579451412540
PROPAGANDA = 508701809557110834

# Bot Stuff
BOT_SPAM = 880957686122958880

# Operations
COMMAND = 341763940046340098  # Voice
DEPLOYED = 355512941816053770  # Voice


####################
# SSG RANKS
####################

PROSPECT = 949865539684151338  # Received upon joining
VERIFIED = 622935992281726976  # After interview
ASSOCIATE = 527354143199854593  # Newcomer workshop
CONTRACTOR = 465993518062501914  # Good rifleman
OPERATOR = 512413279646121985  # Good TL
TECHNICIAN = 679768937847848963  # 1+ SMEs
SPECIALIST = 561839586309963777  # Good actual
ADVISOR = 679769219415539713  # 1+ SMEs + Good actual

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
# SSG SPECIAL ROLES
####################

UNIT_STAFF = 655465074982518805

SERVER_HAMSTER = 848321186336473189
CURATOR = 392773303770677248
MISSION_BUILDER = 843388445317267476
ZEUS = 796178478142849048


####################
# SSG SMES
####################

SME_RW_PILOT = 663401116863823894
SME_FW_PILOT = 672201597983391794
SME_JTAC = 663401127693254678
SME_MEDIC = 663401119476613140
SME_HEAVY_WEAPONS = 759399628096536586
SME_MARKSMAN = 663401122131869736
SME_BREACHER = 663401114561150976
SME_MECHANISED = 892887819540918282
SME_RPV_SO = 752013238820012092
SME_ARTILLERY = 752013234633965589
SME_ARTILLERY = 752013234633965589
SME_MENTOR = 932557163212202045

SME_ROLES = (SME_RW_PILOT, SME_FW_PILOT, SME_JTAC, SME_MEDIC, SME_HEAVY_WEAPONS, SME_MARKSMAN, SME_BREACHER, SME_MECHANISED, SME_RPV_SO, SME_ARTILLERY, SME_MENTOR)


####################
# SSG EMOJIS
####################

GREEN = 383012343526850571
RED = 383012306063327235
YELLOW = 383012329354428418
BLUE = 383012363948785670

PEPE_GUN = "<:PepeGun:803463784617345045>"
