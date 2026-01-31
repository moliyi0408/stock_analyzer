def entry_plan(df, support):
    return [
        round(support * 0.98, 2),
        round(support * 0.93, 2)
    ]
