from scripts_dpv1.load_pp_card import parse_race_type

tests = [
    ("™Alw 34100n1x 4½ Furlongs 3&up, F & M",       "ALLOWANCE"),
    ("™'Alw 34100n2L 6½ Furlongs 3&up, F & M",      "ALLOWANCE"),
    ("'Alw 36600n4L 7 Furlongs 3&up",               "ALLOWANCE"),
    ("™CTOaks-G2 7 Furlongs 3yo Fillies",           "STAKES"),
    ("CTClssic-G2 1„ Mile 3&up",                    "STAKES"),
    ("™Autumn50K 4½ Furlongs 3&up, F & M",          "STAKES"),
    ("Alw 34100n2L 6½ Furlongs",                    "ALLOWANCE"),
    ("MC 12500 5 Furlongs",                         "MAIDENCLAIMING"),
]
for cond, want in tests:
    got = parse_race_type(cond)
    mark = "OK " if got == want else "FAIL"
    print(f"{mark} want={want:<25} got={got}   | {cond[:50]}")