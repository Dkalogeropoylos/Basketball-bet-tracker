
import pandas as pd
import streamlit as st


PAGE_SIZE = 1000


# ==========================================
# LOAD ALL ANALYSIS DATA
# ==========================================

def load_analysis_data(
    supabase
):

    rows = []
    start = 0

    try:

        while True:

            response = (
                supabase
                .table("bets")
                .select("*")
                .eq(
                    "is_deleted",
                    False
                )
                .neq(
                    "result",
                    "Pending"
                )
                .order(
                    "bet_date",
                    desc=False
                )
                .order(
                    "bet_number",
                    desc=False
                )
                .range(
                    start,
                    start + PAGE_SIZE - 1
                )
                .execute()
            )

            page = (
                response.data
                or []
            )

            rows.extend(page)

            if len(page) < PAGE_SIZE:
                break

            start += PAGE_SIZE


    except Exception as e:

        st.error(
            f"Could not load analysis data: {e}"
        )

        return pd.DataFrame()


    if not rows:

        return pd.DataFrame()


    return pd.DataFrame(rows)


# ==========================================
# DISPLAY SELECTION
# ==========================================

def format_selection(row):

    scope = row.get("scope")

    subject = (
        row.get("subject")
        or ""
    )

    selection_2 = (
        row.get("selection_2")
        or ""
    )

    market = (
        row.get("market")
        or ""
    )

    side = (
        row.get("side")
        or ""
    )

    line = row.get("line")


    if scope == "OUTRIGHT":

        if market == "Final Matchup":

            if selection_2:

                return (
                    f"{subject} vs "
                    f"{selection_2}"
                )

            return subject


        if market == "Straight Forecast":

            if selection_2:

                return (
                    f"1st: {subject} | "
                    f"2nd: {selection_2}"
                )

            return (
                f"1st: {subject}"
            )


        if (
            market.startswith("Top ")
            and market.endswith(" - Team")
        ):

            if selection_2:

                return (
                    f"{subject} "
                    f"({selection_2})"
                )

            return subject


        return subject


    result = side


    if pd.notna(line):

        result = (
            f"{result} "
            f"{float(line):g}"
        ).strip()


    return result


# ==========================================
# ANALYSIS PAGE
# ==========================================

def analysis_page(
    supabase,
    load_tipsters
):

    st.header(
        "📊 Analysis"
    )


    df = load_analysis_data(
        supabase
    )


    if df.empty:

        st.info(
            "No settled bets available "
            "for analysis yet."
        )

        return


    # ======================================
    # TIPSTERS
    # ======================================

    tipsters = load_tipsters()


    tipster_map = {
        t["id"]:
            t["name"]
        for t in tipsters
    }


    df["tipster_name"] = (
        df["tipster_id"]
        .map(
            tipster_map
        )
    )


    # ======================================
    # NUMERIC DATA
    # ======================================

    numeric_columns = [
        "stake",
        "profit",
        "market_odds",
        "my_odds",
        "p_market",
        "p_you",
        "edge_pp",
        "ev_pct",
        "cashout_return"
    ]


    for column in numeric_columns:

        if column in df.columns:

            df[column] = (
                pd.to_numeric(
                    df[column],
                    errors="coerce"
                )
            )


    # ======================================
    # FILTERS
    # ======================================

    st.subheader(
        "Filters"
    )


    c1, c2 = st.columns(2)


    with c1:

        scope_options = (
            ["All"]
            + sorted(
                df["scope"]
                .dropna()
                .unique()
                .tolist()
            )
        )


        scope_filter = st.selectbox(
            "Bet Type",
            scope_options,
            key="analysis_scope"
        )


    with c2:

        league_options = (
            ["All"]
            + sorted(
                df["league"]
                .dropna()
                .unique()
                .tolist()
            )
        )


        league_filter = st.selectbox(
            "League",
            league_options,
            key="analysis_league"
        )


    # Market depends on selected scope

    market_source = df.copy()


    if scope_filter != "All":

        market_source = (
            market_source[
                market_source["scope"]
                == scope_filter
            ]
        )


    market_options = (
        ["All"]
        + sorted(
            market_source["market"]
            .dropna()
            .unique()
            .tolist()
        )
    )


    c1, c2 = st.columns(2)


    with c1:

        market_filter = st.selectbox(
            "Market",
            market_options,
            key="analysis_market"
        )


    with c2:

        side_options = (
            ["All"]
            + sorted(
                df["side"]
                .dropna()
                .unique()
                .tolist()
            )
        )


        side_filter = st.selectbox(
            "Side",
            side_options,
            key="analysis_side"
        )


    c1, c2 = st.columns(2)


    with c1:

        origin_filter = st.selectbox(
            "Origin",
            [
                "All",
                "SELF",
                "TIPSTER"
            ],
            key="analysis_origin"
        )


    with c2:

        confidence_options = (
            ["All"]
            + sorted(
                df["confidence"]
                .dropna()
                .unique()
                .tolist()
            )
        )


        confidence_filter = (
            st.selectbox(
                "Confidence",
                confidence_options,
                key="analysis_confidence"
            )
        )


    # ======================================
    # SPECIFIC TIPSTER
    # ======================================

    saved_tipsters = sorted(
        [
            t["name"]
            for t in tipsters
            if t.get("name")
        ]
    )


    c1, c2 = st.columns(2)


    with c1:

        specific_tipster = (
            st.selectbox(
                "Specific Tipster",
                ["All"]
                + saved_tipsters,
                key="analysis_tipster"
            )
        )


    with c2:

        result_filter = (
            st.selectbox(
                "Result",
                [
                    "All",
                    "Win",
                    "Loss",
                    "Cashout",
                    "Void"
                ],
                key="analysis_result"
            )
        )


    c1, c2 = st.columns(2)


    with c1:

        reason_options = (
            ["All"]
            + sorted(
                df[
                    "primary_reason"
                ]
                .dropna()
                .unique()
                .tolist()
            )
        )


        reason_filter = (
            st.selectbox(
                "Primary Reason",
                reason_options,
                key="analysis_reason"
            )
        )


    with c2:

        player_source = (
            df[
                df["scope"]
                == "PLAYER"
            ]["subject"]
            .dropna()
            .unique()
            .tolist()
        )


        player_options = (
            ["All"]
            + sorted(
                player_source
            )
        )


        player_filter = (
            st.selectbox(
                "Player",
                player_options,
                key="analysis_player"
            )
        )


    # ======================================
    # APPLY FILTERS
    # ======================================

    filtered = df.copy()


    if scope_filter != "All":

        filtered = filtered[
            filtered["scope"]
            == scope_filter
        ]


    if league_filter != "All":

        filtered = filtered[
            filtered["league"]
            == league_filter
        ]


    if market_filter != "All":

        filtered = filtered[
            filtered["market"]
            == market_filter
        ]


    if side_filter != "All":

        filtered = filtered[
            filtered["side"]
            == side_filter
        ]


    if origin_filter != "All":

        filtered = filtered[
            filtered["origin"]
            == origin_filter
        ]


    if confidence_filter != "All":

        filtered = filtered[
            filtered["confidence"]
            == confidence_filter
        ]


    if specific_tipster != "All":

        filtered = filtered[
            filtered["tipster_name"]
            == specific_tipster
        ]


    if result_filter != "All":

        filtered = filtered[
            filtered["result"]
            == result_filter
        ]


    if reason_filter != "All":

        filtered = filtered[
            filtered[
                "primary_reason"
            ]
            == reason_filter
        ]


    if player_filter != "All":

        filtered = filtered[
            filtered["subject"]
            == player_filter
        ]


    if filtered.empty:

        st.warning(
            "No bets match these filters."
        )

        return


    # ======================================
    # FINANCIAL PERFORMANCE
    # ======================================

    performance = filtered[
        filtered["result"]
        .isin([
            "Win",
            "Loss",
            "Cashout"
        ])
    ].copy()


    st.divider()

    st.subheader(
        "💰 Financial Performance"
    )


    if not performance.empty:

        total_bets = len(
            performance
        )


        total_stake = (
            performance["stake"]
            .fillna(0)
            .sum()
        )


        total_profit = (
            performance["profit"]
            .fillna(0)
            .sum()
        )


        total_return = (
            total_stake
            + total_profit
        )


        realized_roi = (
            total_profit
            / total_stake
            * 100
            if total_stake > 0
            else 0
        )


        decisions = performance[
            performance["result"]
            .isin([
                "Win",
                "Loss"
            ])
        ]


        if not decisions.empty:

            wins = (
                decisions["result"]
                .eq("Win")
                .sum()
            )


            win_rate = (
                wins
                / len(decisions)
                * 100
            )


            win_rate_text = (
                f"{win_rate:.2f}%"
            )


        else:

            win_rate_text = "—"


        c1, c2, c3, c4 = (
            st.columns(4)
        )


        with c1:

            st.metric(
                "Bets",
                total_bets
            )


        with c2:

            st.metric(
                "Total Stake",
                f"{total_stake:.2f}"
            )


        with c3:

            st.metric(
                "Total Return",
                f"{total_return:.2f}"
            )


        with c4:

            st.metric(
                "Net Profit",
                f"{total_profit:+.2f}"
            )


        c1, c2 = st.columns(2)


        with c1:

            st.metric(
                "Realized ROI",
                f"{realized_roi:+.2f}%"
            )


        with c2:

            st.metric(
                "Win Rate",
                win_rate_text
            )


    # ======================================
    # CASHOUT PERFORMANCE
    # ======================================

    cashouts = filtered[
        filtered["result"]
        == "Cashout"
    ].copy()


    if not cashouts.empty:

        cashout_stake = (
            cashouts["stake"]
            .fillna(0)
            .sum()
        )


        cashout_return = (
            cashouts[
                "cashout_return"
            ]
            .fillna(0)
            .sum()
        )


        cashout_profit = (
            cashouts["profit"]
            .fillna(0)
            .sum()
        )


        cashout_roi = (
            cashout_profit
            / cashout_stake
            * 100
            if cashout_stake > 0
            else 0
        )


        st.subheader(
            "💰 Cashout Performance"
        )


        c1, c2, c3, c4 = (
            st.columns(4)
        )


        with c1:

            st.metric(
                "Cashouts",
                len(cashouts)
            )


        with c2:

            st.metric(
                "Cashout Return",
                f"{cashout_return:.2f}"
            )


        with c3:

            st.metric(
                "Cashout Profit",
                f"{cashout_profit:+.2f}"
            )


        with c4:

            st.metric(
                "Cashout ROI",
                f"{cashout_roi:+.2f}%"
            )


    # ======================================
    # EXPECTED VS ACTUAL
    # ======================================

    value_sample = filtered[
        filtered["ev_pct"]
        .notna()
        & filtered["result"]
        .isin([
            "Win",
            "Loss",
            "Cashout"
        ])
    ].copy()


    if not value_sample.empty:

        value_stake = (
            value_sample["stake"]
            .fillna(0)
            .sum()
        )


        value_sample[
            "expected_profit"
        ] = (
            value_sample["stake"]
            * value_sample["ev_pct"]
            / 100
        )


        expected_profit = (
            value_sample[
                "expected_profit"
            ]
            .fillna(0)
            .sum()
        )


        expected_roi = (
            expected_profit
            / value_stake
            * 100
            if value_stake > 0
            else 0
        )


        actual_profit = (
            value_sample["profit"]
            .fillna(0)
            .sum()
        )


        actual_roi = (
            actual_profit
            / value_stake
            * 100
            if value_stake > 0
            else 0
        )


        roi_difference = (
            actual_roi
            - expected_roi
        )


        st.divider()

        st.subheader(
            "📐 Expected vs Actual"
        )


        st.caption(
            "Compares the value estimated "
            "at entry with the money "
            "actually made."
        )


        c1, c2, c3 = (
            st.columns(3)
        )


        with c1:

            st.metric(
                "Expected ROI at Entry",
                f"{expected_roi:+.2f}%"
            )


        with c2:

            st.metric(
                "Realized ROI",
                f"{actual_roi:+.2f}%"
            )


        with c3:

            st.metric(
                "ROI Difference",
                f"{roi_difference:+.2f} pp"
            )


        c1, c2 = st.columns(2)


        with c1:

            st.metric(
                "Expected Profit",
                f"{expected_profit:+.2f}"
            )


        with c2:

            st.metric(
                "Actual Profit",
                f"{actual_profit:+.2f}"
            )


    # ======================================
    # PROBABILITY CALIBRATION
    # ======================================

    calibration = filtered[
        filtered["p_you"]
        .notna()
        & filtered["result"]
        .isin([
            "Win",
            "Loss"
        ])
    ].copy()


    if not calibration.empty:

        calibration[
            "actual_win"
        ] = (
            calibration["result"]
            .eq("Win")
            .astype(int)
        )


        avg_probability = (
            calibration["p_you"]
            .mean()
            * 100
        )


        actual_hit_rate = (
            calibration[
                "actual_win"
            ]
            .mean()
            * 100
        )


        calibration_difference = (
            actual_hit_rate
            - avg_probability
        )


        st.divider()

        st.subheader(
            "🎯 Probability Calibration"
        )


        st.caption(
            "Cashouts are excluded. "
            "This checks whether your "
            "estimated probabilities "
            "match actual Win/Loss outcomes."
        )


        c1, c2, c3, c4 = (
            st.columns(4)
        )


        with c1:

            st.metric(
                "Completed Bets",
                len(calibration)
            )


        with c2:

            st.metric(
                "Avg Your Probability",
                f"{avg_probability:.2f}%"
            )


        with c3:

            st.metric(
                "Actual Hit Rate",
                f"{actual_hit_rate:.2f}%"
            )


        with c4:

            st.metric(
                "Calibration Difference",
                f"{calibration_difference:+.2f} pp"
            )


        calibration[
            "probability_pct"
        ] = (
            calibration["p_you"]
            * 100
        )


        bins = [
            0,
            40,
            50,
            55,
            60,
            65,
            70,
            80,
            100.01
        ]


        labels = [
            "<40%",
            "40-50%",
            "50-55%",
            "55-60%",
            "60-65%",
            "65-70%",
            "70-80%",
            "80%+"
        ]


        calibration[
            "Probability Band"
        ] = pd.cut(
            calibration[
                "probability_pct"
            ],
            bins=bins,
            labels=labels,
            right=False
        )


        calibration_table = (
            calibration
            .groupby(
                "Probability Band",
                observed=True
            )
            .agg(
                Bets=(
                    "id",
                    "count"
                ),
                Your_Probability=(
                    "probability_pct",
                    "mean"
                ),
                Actual_Hit_Rate=(
                    "actual_win",
                    "mean"
                )
            )
            .reset_index()
        )


        calibration_table[
            "Actual_Hit_Rate"
        ] = (
            calibration_table[
                "Actual_Hit_Rate"
            ]
            * 100
        )


        calibration_table[
            "Difference_pp"
        ] = (
            calibration_table[
                "Actual_Hit_Rate"
            ]
            - calibration_table[
                "Your_Probability"
            ]
        )


        calibration_table = (
            calibration_table
            .rename(
                columns={
                    "Your_Probability":
                        "Your Probability %",
                    "Actual_Hit_Rate":
                        "Actual Hit Rate %",
                    "Difference_pp":
                        "Difference pp"
                }
            )
        )


        for column in [
            "Your Probability %",
            "Actual Hit Rate %",
            "Difference pp"
        ]:

            calibration_table[
                column
            ] = (
                calibration_table[
                    column
                ]
                .round(2)
            )


        st.subheader(
            "Calibration by Probability Range"
        )


        st.dataframe(
            calibration_table,
            use_container_width=True,
            hide_index=True
        )


    # ======================================
    # CUMULATIVE PROFIT
    # ======================================

    if not performance.empty:

        chart_df = (
            performance
            .copy()
            .sort_values(
                [
                    "bet_date",
                    "bet_number"
                ]
            )
        )


        chart_df[
            "Cumulative Profit"
        ] = (
            chart_df["profit"]
            .fillna(0)
            .cumsum()
        )


        chart_df["Bet"] = range(
            1,
            len(chart_df) + 1
        )


        chart_df = (
            chart_df
            .set_index("Bet")
        )


        st.divider()

        st.subheader(
            "📈 Cumulative Profit"
        )


        st.line_chart(
            chart_df[
                ["Cumulative Profit"]
            ]
        )


    # ======================================
    # PERFORMANCE BY MARKET
    # ======================================

    if not performance.empty:

        market_summary = (
            performance
            .groupby(
                "market",
                dropna=False
            )
            .agg(
                Bets=(
                    "id",
                    "count"
                ),
                Stake=(
                    "stake",
                    "sum"
                ),
                Profit=(
                    "profit",
                    "sum"
                )
            )
            .reset_index()
        )


        market_summary[
            "ROI %"
        ] = (
            market_summary["Profit"]
            / market_summary["Stake"]
            * 100
        )


        market_summary = (
            market_summary
            .sort_values(
                "ROI %",
                ascending=False
            )
        )


        for column in [
            "Stake",
            "Profit",
            "ROI %"
        ]:

            market_summary[
                column
            ] = (
                market_summary[
                    column
                ]
                .round(2)
            )


        st.subheader(
            "Performance by Market"
        )


        st.dataframe(
            market_summary,
            use_container_width=True,
            hide_index=True
        )


    # ======================================
    # FILTERED BETS
    # ======================================

    st.subheader(
        "Filtered Bets"
    )


    filtered = (
        filtered.copy()
    )


    filtered[
        "selection_display"
    ] = filtered.apply(
        format_selection,
        axis=1
    )


    columns_to_show = [
        "bet_date",
        "league",
        "scope",
        "event",
        "subject",
        "market",
        "selection_display",
        "market_odds",
        "my_odds",
        "origin",
        "tipster_name",
        "confidence",
        "primary_reason",
        "result",
        "cashout_return",
        "ev_pct",
        "profit"
    ]


    visible_columns = [
        column
        for column
        in columns_to_show
        if column
        in filtered.columns
    ]


    display_df = (
        filtered[
            visible_columns
        ]
        .sort_values(
            "bet_date",
            ascending=False
        )
    )


    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
