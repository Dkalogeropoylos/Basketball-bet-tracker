
import os
import streamlit as st
import pandas as pd

from datetime import date, datetime, timezone
from supabase import create_client

from options import (
    SPORT,
    LEAGUES,
    BOOKMAKERS,
    PLAYER_MARKETS,
    TEAM_MARKETS,
    MATCH_MARKETS,
    OUTRIGHT_MARKETS,
    PERIODS,
    REASONS
)

from analytics import analysis_page
from suggestions import suggestions_page


# ==========================================
# PAGE CONFIG
# ==========================================

st.set_page_config(
    page_title="Bet Tracker",
    page_icon="🏀",
    layout="centered"
)


# ==========================================
# SUPABASE CONNECTION
# ==========================================

def get_secret(name):

    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name)


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_PUBLISHABLE_KEY")


if not SUPABASE_URL or not SUPABASE_KEY:

    st.error(
        "Supabase credentials are missing."
    )

    st.stop()


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ==========================================
# SESSION STATE
# ==========================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "refresh_token" not in st.session_state:
    st.session_state.refresh_token = None

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "delete_confirm_id" not in st.session_state:
    st.session_state.delete_confirm_id = None


# Restore auth after Streamlit rerun
if (
    st.session_state.logged_in
    and st.session_state.access_token
    and st.session_state.refresh_token
):

    try:

        session_response = (
            supabase.auth.set_session(
                st.session_state.access_token,
                st.session_state.refresh_token
            )
        )

        if session_response.session:

            st.session_state.access_token = (
                session_response
                .session
                .access_token
            )

            st.session_state.refresh_token = (
                session_response
                .session
                .refresh_token
            )

    except Exception:

        st.session_state.logged_in = False


# ==========================================
# HELPERS
# ==========================================

def now_utc():

    return (
        datetime
        .now(timezone.utc)
        .isoformat()
    )


def safe_index(
    options,
    value,
    default=0
):

    try:
        return options.index(value)

    except Exception:
        return default


def get_market_options(scope):

    if scope == "PLAYER":
        return PLAYER_MARKETS

    if scope == "TEAM":
        return TEAM_MARKETS

    if scope == "MATCH":
        return MATCH_MARKETS

    if scope == "OUTRIGHT":
        return OUTRIGHT_MARKETS

    return []


def outright_needs_second_selection(
    market
):

    return (
        market in [
            "Final Matchup",
            "Straight Forecast"
        ]
        or (
            market.startswith("Top ")
            and market.endswith(" - Team")
        )
    )


def outright_selection_labels(
    market
):

    if market == "Final Matchup":

        return (
            "Team 1",
            "Team 2"
        )


    if market == "Straight Forecast":

        return (
            "1st Place",
            "2nd Place"
        )


    if (
        market.startswith("Top ")
        and market.endswith(" - Team")
    ):

        return (
            "Player",
            "Team"
        )


    if market.startswith("Top "):

        return (
            "Player",
            None
        )


    return (
        "Selection",
        None
    )


def format_bet_selection(
    bet
):

    scope = bet.get("scope")

    market = (
        bet.get("market")
        or ""
    )

    subject = (
        bet.get("subject")
        or ""
    )

    selection_2 = (
        bet.get("selection_2")
        or ""
    )

    side = bet.get("side")
    line = bet.get("line")


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
            and market.endswith(
                " - Team"
            )
        ):

            if selection_2:

                return (
                    f"{subject} "
                    f"({selection_2})"
                )

            return subject


        return subject


    text_value = side or ""


    if line is not None:

        text_value = (
            f"{text_value} "
            f"{float(line):g}"
        ).strip()


    return text_value


def calculate_metrics(
    market_odds,
    my_odds=None,
    tipster_posted_odds=None
):

    p_market = (
        1 / float(market_odds)
    )

    p_you = None
    edge_pp = None
    ev_pct = None

    if my_odds:

        p_you = (
            1 / float(my_odds)
        )

        edge_pp = (
            p_you - p_market
        ) * 100

        ev_pct = (
            p_you
            * float(market_odds)
            - 1
        ) * 100


    price_deterioration_pp = None

    if tipster_posted_odds:

        posted_probability = (
            1
            / float(
                tipster_posted_odds
            )
        )

        price_deterioration_pp = (
            p_market
            - posted_probability
        ) * 100


    return {

        "p_market":
            p_market,

        "p_you":
            p_you,

        "edge_pp":
            edge_pp,

        "ev_pct":
            ev_pct,

        "price_deterioration_pp":
            price_deterioration_pp
    }


def calculate_profit(
    result,
    stake,
    market_odds
):

    stake = float(stake)
    odds = float(market_odds)

    if result == "Win":

        return round(
            stake * (odds - 1),
            2
        )

    if result == "Loss":

        return round(
            -stake,
            2
        )

    return 0.0


# ==========================================
# LOGIN
# ==========================================

def login_page():

    st.title(
        "🏀 Bet Tracker"
    )

    st.caption(
        "Sign in to your personal tracker"
    )


    with st.form(
        "login_form"
    ):

        email = st.text_input(
            "Email"
        )

        password = st.text_input(
            "Password",
            type="password"
        )

        submitted = (
            st.form_submit_button(
                "Login",
                use_container_width=True
            )
        )


    if submitted:

        if not email or not password:

            st.warning(
                "Enter email and password."
            )

            return


        try:

            response = (
                supabase
                .auth
                .sign_in_with_password({
                    "email":
                        email,

                    "password":
                        password
                })
            )


            if (
                response.session
                and response.user
            ):

                st.session_state.logged_in = (
                    True
                )

                st.session_state.access_token = (
                    response
                    .session
                    .access_token
                )

                st.session_state.refresh_token = (
                    response
                    .session
                    .refresh_token
                )

                st.session_state.user_id = (
                    response.user.id
                )

                st.session_state.user_email = (
                    response.user.email
                )

                st.rerun()


        except Exception as e:

            st.error(
                f"Login failed: {e}"
            )


def logout():

    try:

        supabase.auth.sign_out()

    except Exception:
        pass

    st.session_state.clear()

    st.rerun()


# ==========================================
# TIPSTERS
# ==========================================

def load_tipsters():

    try:

        response = (
            supabase
            .table("tipsters")
            .select("id,name")
            .order("name")
            .execute()
        )

        return response.data or []

    except Exception:

        return []


def create_tipster(name):

    name = name.strip()

    if not name:
        return None


    response = (
        supabase
        .table("tipsters")
        .insert({

            "user_id":
                st.session_state.user_id,

            "name":
                name
        })
        .execute()
    )


    if response.data:

        return response.data[0]

    return None


# ==========================================
# COUNTERS
# ==========================================

def get_total_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .execute()
    )

    return response.count or 0


def get_pending_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .eq(
            "result",
            "Pending"
        )
        .execute()
    )

    return response.count or 0


def get_settled_bets_count():

    response = (
        supabase
        .table("bets")
        .select(
            "id",
            count="exact"
        )
        .eq(
            "is_deleted",
            False
        )
        .neq(
            "result",
            "Pending"
        )
        .execute()
    )

    return response.count or 0


# ==========================================
# LOAD BETS
# ==========================================

def load_pending_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                False
            )
            .eq(
                "result",
                "Pending"
            )
            .order(
                "bet_date",
                desc=False
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load pending bets: {e}"
        )

        return []


def load_history_bets():

    try:

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
                desc=True
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load history: {e}"
        )

        return []


def load_active_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                False
            )
            .order(
                "bet_date",
                desc=True
            )
            .order(
                "bet_number",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load bets: {e}"
        )

        return []


def load_deleted_bets():

    try:

        response = (
            supabase
            .table("bets")
            .select("*")
            .eq(
                "is_deleted",
                True
            )
            .order(
                "deleted_at",
                desc=True
            )
            .execute()
        )

        return response.data or []


    except Exception as e:

        st.error(
            f"Could not load Trash: {e}"
        )

        return []


# ==========================================
# SETTLE
# ==========================================

def settle_bet(
    bet_id,
    result,
    stake,
    market_odds
):

    profit = calculate_profit(
        result,
        stake,
        market_odds
    )


    response = (
        supabase
        .table("bets")
        .update({

            "result":
                result,

            "profit":
                profit,

            "settled_at":
                now_utc(),

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data



# ==========================================
# CASHOUT
# ==========================================

def settle_cashout(
    bet_id,
    stake,
    cashout_return
):

    stake = float(stake)
    cashout_return = float(
        cashout_return
    )

    profit = round(
        cashout_return - stake,
        2
    )

    timestamp = now_utc()

    response = (
        supabase
        .table("bets")
        .update({

            "result":
                "Cashout",

            "cashout_return":
                cashout_return,

            "profit":
                profit,

            "cashout_at":
                timestamp,

            "settled_at":
                timestamp,

            "updated_at":
                timestamp
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data


# ==========================================
# SOFT DELETE / RESTORE
# ==========================================

def soft_delete_bet(bet_id):

    response = (
        supabase
        .table("bets")
        .update({

            "is_deleted":
                True,

            "deleted_at":
                now_utc(),

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data


def restore_bet(bet_id):

    response = (
        supabase
        .table("bets")
        .update({

            "is_deleted":
                False,

            "deleted_at":
                None,

            "updated_at":
                now_utc()
        })
        .eq(
            "id",
            bet_id
        )
        .eq(
            "user_id",
            st.session_state.user_id
        )
        .execute()
    )

    return response.data



# ==========================================
# ENTRY AUTOCOMPLETE
# ==========================================

def load_entry_suggestions():

    rows = []
    page_size = 1000
    start = 0

    try:

        while True:

            response = (
                supabase
                .table("bets")
                .select(
                    "event,scope,subject,"
                    "selection_2,market"
                )
                .eq(
                    "is_deleted",
                    False
                )
                .range(
                    start,
                    start + page_size - 1
                )
                .execute()
            )

            page = response.data or []

            rows.extend(page)

            if len(page) < page_size:
                break

            start += page_size

    except Exception:

        rows = []


    regular_events = []
    outright_events = []
    players = []
    teams = []


    for bet in rows:

        scope = bet.get("scope")

        event = (
            bet.get("event")
            or ""
        ).strip()

        subject = (
            bet.get("subject")
            or ""
        ).strip()

        selection_2 = (
            bet.get("selection_2")
            or ""
        ).strip()

        market = (
            bet.get("market")
            or ""
        )


        if event:

            if scope == "OUTRIGHT":

                outright_events.append(
                    event
                )

            else:

                regular_events.append(
                    event
                )


        if scope == "PLAYER":

            if subject:
                players.append(
                    subject
                )


        elif scope == "TEAM":

            if subject:
                teams.append(
                    subject
                )


        elif scope == "OUTRIGHT":

            if market.startswith("Top "):

                if subject:
                    players.append(
                        subject
                    )

                if (
                    market.endswith(" - Team")
                    and selection_2
                ):

                    teams.append(
                        selection_2
                    )


            elif market in [
                "Final Matchup",
                "Straight Forecast"
            ]:

                if subject:
                    teams.append(
                        subject
                    )

                if selection_2:
                    teams.append(
                        selection_2
                    )


            else:

                if subject:
                    teams.append(
                        subject
                    )


    def clean(values):

        unique = {}

        for value in values:

            value = str(
                value
            ).strip()

            if not value:
                continue

            key = value.casefold()

            if key not in unique:
                unique[key] = value


        return sorted(
            unique.values(),
            key=lambda x: x.casefold()
        )


    return {

        "regular_events":
            clean(
                regular_events
            ),

        "outright_events":
            clean(
                outright_events
            ),

        "players":
            clean(
                players
            ),

        "teams":
            clean(
                teams
            )
    }


# ==========================================
# ADD BET
# ==========================================

def add_bet_page():

    st.header("➕ Add Bet")


    # ======================================
    # DATE / LEAGUE
    # ======================================

    col1, col2 = st.columns(2)


    with col1:

        bet_date = st.date_input(
            "Bet Date",
            value=date.today()
        )


    with col2:

        league = st.selectbox(
            "League",
            LEAGUES
        )


    # ======================================
    # SCOPE
    # ======================================

    scope = st.radio(
        "Bet Type",
        [
            "PLAYER",
            "TEAM",
            "MATCH",
            "OUTRIGHT"
        ],
        horizontal=True
    )


    entry_suggestions = (
        load_entry_suggestions()
    )


    event_options = (
        entry_suggestions[
            "outright_events"
        ]
        if scope == "OUTRIGHT"
        else entry_suggestions[
            "regular_events"
        ]
    )


    event = st.selectbox(
        (
            "Competition / Event"
            if scope == "OUTRIGHT"
            else "Event"
        ),
        event_options,
        index=None,
        placeholder=(
            "Search or enter competition..."
            if scope == "OUTRIGHT"
            else "Search or enter matchup..."
        ),
        accept_new_options=True
    )


    st.divider()


    subject = None
    selection_2 = None
    line = None
    side = None


    # ======================================
    # OUTRIGHT
    # ======================================

    if scope == "OUTRIGHT":

        market = st.selectbox(
            "Outright Market",
            OUTRIGHT_MARKETS
        )


        label_1, label_2 = (
            outright_selection_labels(
                market
            )
        )


        if label_1 == "Player":

            outright_options_1 = (
                entry_suggestions[
                    "players"
                ]
            )

        else:

            outright_options_1 = (
                entry_suggestions[
                    "teams"
                ]
            )


        subject = st.selectbox(
            label_1,
            outright_options_1,
            index=None,
            placeholder=(
                f"Search or enter "
                f"{label_1.lower()}..."
            ),
            accept_new_options=True
        )


        if label_2:

            selection_2 = (
                st.selectbox(
                    label_2,
                    entry_suggestions[
                        "teams"
                    ],
                    index=None,
                    placeholder=(
                        f"Search or enter "
                        f"{label_2.lower()}..."
                    ),
                    accept_new_options=True
                )
            )


        period = "Full Competition"


        st.caption(
            "🏆 This bet will be stored "
            "separately from regular "
            "pending bets."
        )


    # ======================================
    # REGULAR BETS
    # ======================================

    else:

        if scope == "PLAYER":

            subject = st.selectbox(
                "Player",
                entry_suggestions[
                    "players"
                ],
                index=None,
                placeholder=(
                    "Search or enter player..."
                ),
                accept_new_options=True
            )


        elif scope == "TEAM":

            subject = st.selectbox(
                "Team",
                entry_suggestions[
                    "teams"
                ],
                index=None,
                placeholder=(
                    "Search or enter team..."
                ),
                accept_new_options=True
            )


        market = st.selectbox(
            "Market",
            get_market_options(
                scope
            )
        )


        period = st.selectbox(
            "Period",
            PERIODS
        )


        if market == "Moneyline":

            side = st.radio(
                "Selection",
                [
                    "Home",
                    "Away"
                ],
                horizontal=True
            )


        elif (
            market
            == "Handicap / Spread"
        ):

            side = st.radio(
                "Selection",
                [
                    "Home",
                    "Away"
                ],
                horizontal=True
            )


            line = st.number_input(
                "Line",
                step=0.5,
                format="%.1f"
            )


        else:

            side = st.radio(
                "Side",
                [
                    "Over",
                    "Under"
                ],
                horizontal=True
            )


            line = st.number_input(
                "Line",
                step=0.5,
                format="%.1f"
            )


    # ======================================
    # BOOKMAKER / ODDS
    # ======================================

    st.divider()


    col1, col2 = st.columns(2)


    with col1:

        bookmaker = st.selectbox(
            "Bookmaker",
            BOOKMAKERS
        )


    with col2:

        market_odds = st.number_input(
            "Odds Taken",
            min_value=1.01,
            value=1.90,
            step=0.01,
            format="%.2f"
        )


    # ======================================
    # ORIGIN
    # ======================================

    origin = st.radio(
        "Origin",
        [
            "SELF",
            "TIPSTER"
        ],
        horizontal=True
    )


    my_odds = None
    tipster_id = None
    tipster_posted_odds = None
    has_own_reasoning = False
    primary_reason = None
    secondary_reason = None
    confidence = None


    # ======================================
    # SELF
    # ======================================

    if origin == "SELF":

        my_odds = st.number_input(
            "My Fair Odds",
            min_value=1.01,
            value=1.80,
            step=0.01,
            format="%.2f"
        )


        confidence = st.radio(
            "Confidence",
            [
                "Low",
                "Medium",
                "High"
            ],
            index=1,
            horizontal=True
        )


        reason_options = (
            ["Select reason..."]
            + REASONS
        )

        primary_reason = (
            st.selectbox(
                "Primary Reason",
                reason_options,
                index=reason_options.index(
                    "Projection Edge"
                )
            )
        )


        secondary_options = (
            ["None"]
            + [
                reason
                for reason in REASONS
                if reason
                != primary_reason
            ]
        )


        secondary_reason = (
            st.selectbox(
                "Secondary Reason",
                secondary_options
            )
        )


        has_own_reasoning = True


    # ======================================
    # TIPSTER
    # ======================================

    else:

        tipsters = load_tipsters()


        tipster_map = {
            t["name"]:
                t["id"]
            for t in tipsters
        }


        existing_names = list(
            tipster_map.keys()
        )


        tipster_choice = (
            st.selectbox(
                "Tipster",
                [
                    "+ Add new tipster"
                ]
                + existing_names
            )
        )


        if (
            tipster_choice
            == "+ Add new tipster"
        ):

            new_tipster = (
                st.text_input(
                    "New Tipster Name"
                )
            )


            if st.button(
                "Save Tipster"
            ):

                try:

                    record = (
                        create_tipster(
                            new_tipster
                        )
                    )


                    if record:

                        st.success(
                            "Tipster saved."
                        )

                        st.rerun()


                except Exception as e:

                    st.error(
                        str(e)
                    )


        else:

            tipster_id = (
                tipster_map[
                    tipster_choice
                ]
            )


        add_posted_odds = (
            st.checkbox(
                "I know the tipster's "
                "posted odds"
            )
        )


        if add_posted_odds:

            tipster_posted_odds = (
                st.number_input(
                    "Tipster Posted Odds",
                    min_value=1.01,
                    value=1.90,
                    step=0.01,
                    format="%.2f"
                )
            )


        confidence = st.radio(
            "Your Confidence",
            [
                "N/A",
                "Low",
                "Medium",
                "High"
            ],
            index=0,
            horizontal=True
        )


        has_own_reasoning = (
            st.checkbox(
                "I also have my own "
                "reasoning for this bet"
            )
        )


        if has_own_reasoning:

            reason_options = (
                ["Select reason..."]
                + REASONS
            )

            primary_reason = (
                st.selectbox(
                    "Primary Reason",
                    reason_options,
                    index=reason_options.index(
                        "Projection Edge"
                    )
                )
            )


            secondary_options = (
                ["None"]
                + [
                    reason
                    for reason in REASONS
                    if reason
                    != primary_reason
                ]
            )


            secondary_reason = (
                st.selectbox(
                    "Secondary Reason",
                    secondary_options
                )
            )


    # ======================================
    # STAKE / NOTES
    # ======================================

    st.divider()


    stake = st.number_input(
        "Stake",
        min_value=0.01,
        value=10.00,
        step=1.00
    )


    notes = st.text_area(
        "Notes",
        placeholder="Optional"
    )


    # ======================================
    # VALUE PREVIEW
    # ======================================

    if origin == "SELF":

        preview = calculate_metrics(
            market_odds,
            my_odds
        )


        st.info(
            f"Market probability: "
            f"{preview['p_market']*100:.2f}% | "
            f"My probability: "
            f"{preview['p_you']*100:.2f}% | "
            f"Probability Edge: "
            f"{preview['edge_pp']:.2f} pp | "
            f"EV: "
            f"{preview['ev_pct']:.2f}%"
        )


    # ======================================
    # SAVE
    # ======================================

    if st.button(
        "💾 SAVE BET",
        type="primary",
        use_container_width=True
    ):


        if not event.strip():

            st.error(
                "Event / Competition "
                "is required."
            )

            return


        if (
            scope in [
                "PLAYER",
                "TEAM"
            ]
            and not (
                subject
                and subject.strip()
            )
        ):

            st.error(
                "Player / Team is required."
            )

            return


        if scope == "OUTRIGHT":

            if not (
                subject
                and subject.strip()
            ):

                st.error(
                    "Outright selection "
                    "is required."
                )

                return


            if (
                outright_needs_second_selection(
                    market
                )
                and not (
                    selection_2
                    and selection_2.strip()
                )
            ):

                st.error(
                    "The second selection "
                    "is required."
                )

                return


        if (
            origin == "TIPSTER"
            and tipster_id is None
        ):

            st.error(
                "Select or create a tipster."
            )

            return


        if (
            primary_reason
            == "Select reason..."
            and (
                origin == "SELF"
                or (
                    origin == "TIPSTER"
                    and has_own_reasoning
                )
            )
        ):

            st.error(
                "Select a Primary Reason."
            )

            return


        metrics = calculate_metrics(
            market_odds,
            my_odds,
            tipster_posted_odds
        )


        record = {

            "user_id":
                st.session_state.user_id,

            "bet_date":
                bet_date.isoformat(),

            "sport":
                SPORT,

            "league":
                league,

            "event":
                event.strip(),

            "scope":
                scope,

            "subject":
                (
                    subject.strip()
                    if subject
                    else None
                ),

            "selection_2":
                (
                    selection_2.strip()
                    if selection_2
                    else None
                ),

            "market":
                market,

            "period":
                period,

            "side":
                side,

            "line":
                line,

            "bookmaker":
                bookmaker,

            "market_odds":
                market_odds,

            "my_odds":
                my_odds,

            "origin":
                origin,

            "tipster_id":
                tipster_id,

            "tipster_posted_odds":
                tipster_posted_odds,

            "confidence":
                confidence,

            "has_own_reasoning":
                has_own_reasoning,

            "primary_reason":
                (
                    None
                    if primary_reason
                    == "Select reason..."
                    else primary_reason
                ),

            "secondary_reason":
                (
                    None
                    if secondary_reason
                    in [
                        None,
                        "None"
                    ]
                    else secondary_reason
                ),

            "stake":
                stake,

            "result":
                "Pending",

            "p_market":
                metrics["p_market"],

            "p_you":
                metrics["p_you"],

            "edge_pp":
                metrics["edge_pp"],

            "ev_pct":
                metrics["ev_pct"],

            "price_deterioration_pp":
                metrics[
                    "price_deterioration_pp"
                ],

            "profit":
                0,

            "notes":
                (
                    notes.strip()
                    if notes.strip()
                    else None
                )
        }


        try:

            response = (
                supabase
                .table("bets")
                .insert(record)
                .execute()
            )


            if response.data:

                st.success(
                    "✅ Bet saved successfully!"
                )

                st.write(
                    f"Total Bets: "
                    f"{get_total_bets_count()}"
                )


        except Exception as e:

            st.error(
                f"Could not save bet: {e}"
            )


# ==========================================
# PENDING
# ==========================================

def render_pending_group(
    bets,
    tipster_map
):

    if not bets:

        st.info(
            "No pending bets "
            "in this category."
        )

        return


    for bet in bets:

        st.divider()


        if bet["scope"] == "OUTRIGHT":

            title = (
                bet["event"]
                or "Outright"
            )

        elif bet["scope"] == "MATCH":

            title = bet["event"]

        else:

            title = bet["subject"]


        st.subheader(
            title
        )


        selection_text = (
            format_bet_selection(
                bet
            )
        )


        if selection_text:

            st.write(
                f"**{bet['market']}** | "
                f"{selection_text}"
            )

        else:

            st.write(
                f"**{bet['market']}**"
            )


        if bet["scope"] == "OUTRIGHT":

            st.caption(
                f"🏆 {bet['league']} | "
                f"{bet['bookmaker']}"
            )

        else:

            st.caption(
                f"{bet['league']} | "
                f"{bet['period']} | "
                f"{bet['bookmaker']}"
            )


        c1, c2, c3 = st.columns(3)


        with c1:

            st.metric(
                "Odds",
                f"{float(bet['market_odds']):.2f}"
            )


        with c2:

            st.metric(
                "Stake",
                f"{float(bet['stake']):.2f}"
            )


        with c3:

            st.metric(
                "Date",
                bet["bet_date"]
            )


        if bet["origin"] == "SELF":

            if bet["my_odds"] is not None:

                st.caption(
                    f"My Fair Odds: "
                    f"{float(bet['my_odds']):.2f} | "
                    f"EV: "
                    f"{float(bet['ev_pct']):.2f}%"
                )


        else:

            tipster_name = (
                tipster_map.get(
                    bet["tipster_id"],
                    "Unknown Tipster"
                )
            )

            st.caption(
                f"Tipster: "
                f"{tipster_name}"
            )


        # ==================================
        # RESULT BUTTONS
        # ==================================

        win_col, loss_col, void_col = (
            st.columns(3)
        )


        with win_col:

            if st.button(
                "✅ WIN",
                key=f"win_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Win",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        with loss_col:

            if st.button(
                "❌ LOSS",
                key=f"loss_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Loss",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        with void_col:

            if st.button(
                "↩️ PUSH / VOID",
                key=f"void_{bet['id']}",
                use_container_width=True
            ):

                settle_bet(
                    bet["id"],
                    "Void",
                    bet["stake"],
                    bet["market_odds"]
                )

                st.rerun()


        # ==================================
        # CASHOUT
        # ==================================

        with st.expander(
            "💰 Cash Out"
        ):

            cashout_return = (
                st.number_input(
                    "Cashout Return",
                    min_value=0.00,
                    value=float(
                        bet["stake"]
                    ),
                    step=0.50,
                    format="%.2f",
                    key=(
                        f"cashout_return_"
                        f"{bet['id']}"
                    )
                )
            )


            cashout_profit = (
                float(cashout_return)
                - float(bet["stake"])
            )


            st.caption(
                f"Cashout P/L: "
                f"{cashout_profit:+.2f}"
            )


            if st.button(
                "💰 CONFIRM CASH OUT",
                key=f"cashout_{bet['id']}",
                use_container_width=True,
                type="primary"
            ):

                try:

                    settle_cashout(
                        bet["id"],
                        bet["stake"],
                        cashout_return
                    )

                    st.rerun()


                except Exception as e:

                    st.error(
                        f"Could not cash out "
                        f"bet: {e}"
                    )


def pending_bets_page():

    bets = load_pending_bets()


    regular_bets = [
        bet
        for bet in bets
        if bet["scope"]
        != "OUTRIGHT"
    ]


    outright_bets = [
        bet
        for bet in bets
        if bet["scope"]
        == "OUTRIGHT"
    ]


    st.header(
        f"⏳ Pending Bets "
        f"({len(bets)})"
    )


    if not bets:

        st.success(
            "No pending bets 🎉"
        )

        return


    tipsters = load_tipsters()


    tipster_map = {
        t["id"]:
            t["name"]
        for t in tipsters
    }


    regular_tab, outright_tab = (
        st.tabs([
            (
                f"🏀 Regular "
                f"({len(regular_bets)})"
            ),
            (
                f"🏆 Outrights "
                f"({len(outright_bets)})"
            )
        ])
    )


    with regular_tab:

        render_pending_group(
            regular_bets,
            tipster_map
        )


    with outright_tab:

        render_pending_group(
            outright_bets,
            tipster_map
        )


# ==========================================
# HISTORY
# ==========================================

def history_page():

    st.header(
        "📜 Bet History"
    )


    history = load_history_bets()


    if not history:

        st.info(
            "No settled bets yet."
        )

        return


    col1, col2 = st.columns(2)


    with col1:

        scope_filter = st.selectbox(
            "Bet Type",
            [
                "All",
                "PLAYER",
                "TEAM",
                "MATCH",
                "OUTRIGHT"
            ],
            key="history_scope"
        )


    with col2:

        result_filter = st.selectbox(
            "Result",
            [
                "All",
                "Win",
                "Loss",
                "Cashout",
                "Void"
            ],
            key="history_result"
        )


    leagues = sorted(
        list(
            set(
                bet["league"]
                for bet in history
                if bet["league"]
            )
        )
    )


    col1, col2 = st.columns(2)


    with col1:

        league_filter = st.selectbox(
            "League",
            ["All"] + leagues,
            key="history_league"
        )


    with col2:

        origin_filter = st.selectbox(
            "Origin",
            [
                "All",
                "SELF",
                "TIPSTER"
            ],
            key="history_origin"
        )


    filtered = history.copy()


    if scope_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["scope"]
            == scope_filter
        ]


    if result_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["result"]
            == result_filter
        ]


    if league_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["league"]
            == league_filter
        ]


    if origin_filter != "All":

        filtered = [
            bet
            for bet in filtered
            if bet["origin"]
            == origin_filter
        ]


    performance = [
        bet
        for bet in filtered
        if bet["result"]
        in [
            "Win",
            "Loss",
            "Cashout"
        ]
    ]


    total_profit = sum(
        float(
            bet["profit"]
            or 0
        )
        for bet in performance
    )


    total_stake = sum(
        float(
            bet["stake"]
            or 0
        )
        for bet in performance
    )


    roi = (
        total_profit
        / total_stake
        * 100
        if total_stake
        else 0
    )


    c1, c2, c3, c4 = (
        st.columns(4)
    )


    with c1:

        st.metric(
            "Bets",
            len(filtered)
        )


    with c2:

        st.metric(
            "Stake",
            f"{total_stake:.2f}"
        )


    with c3:

        st.metric(
            "Profit",
            f"{total_profit:+.2f}"
        )


    with c4:

        st.metric(
            "ROI",
            f"{roi:+.2f}%"
        )


    rows = []


    for bet in filtered:

        selection = (
            format_bet_selection(
                bet
            )
        )


        if bet["scope"] == "OUTRIGHT":

            subject_display = (
                selection
            )

        elif bet["scope"] == "MATCH":

            subject_display = (
                bet["event"]
            )

        else:

            subject_display = (
                bet["subject"]
            )


        rows.append({

            "Date":
                bet["bet_date"],

            "League":
                bet["league"],

            "Type":
                bet["scope"],

            "Event / Competition":
                bet["event"],

            "Subject / Selection":
                subject_display,

            "Market":
                bet["market"],

            "Selection":
                (
                    selection
                    if bet["scope"]
                    != "OUTRIGHT"
                    else ""
                ),

            "Odds":
                float(
                    bet["market_odds"]
                ),

            "Stake":
                float(
                    bet["stake"]
                ),

            "Origin":
                bet["origin"],

            "Confidence":
                bet["confidence"],

            "Result":
                bet["result"],

            "Cashout Return":
                (
                    float(
                        bet[
                            "cashout_return"
                        ]
                    )
                    if bet.get(
                        "cashout_return"
                    ) is not None
                    else None
                ),

            "Profit":
                float(
                    bet["profit"]
                )
        })


    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )


# ==========================================
# MANAGE / EDIT
# ==========================================

def manage_bets_page():

    st.header(
        "✏️ Manage Bets"
    )


    bets = load_active_bets()


    if not bets:

        st.info(
            "No active bets."
        )

        return


    label_map = {}


    for bet in bets:

        if bet["scope"] == "OUTRIGHT":

            description = (
                format_bet_selection(
                    bet
                )
            )

            label = (
                f"{bet['bet_date']} | "
                f"🏆 {bet['event']} | "
                f"{bet['market']} | "
                f"{description} | "
                f"@{float(bet['market_odds']):.2f} | "
                f"{bet['result']}"
            )


        else:

            subject = (
                bet["event"]
                if bet["scope"] == "MATCH"
                else bet["subject"]
            )


            selection = (
                format_bet_selection(
                    bet
                )
            )


            label = (
                f"{bet['bet_date']} | "
                f"{subject} | "
                f"{bet['market']} "
                f"{selection} | "
                f"@{float(bet['market_odds']):.2f} | "
                f"{bet['result']}"
            )


        label_map[label] = bet


    selected_label = (
        st.selectbox(
            "Choose Bet",
            list(
                label_map.keys()
            )
        )
    )


    bet = label_map[
        selected_label
    ]


    bet_id = bet["id"]


    st.divider()

    st.subheader(
        "Edit Bet"
    )


    # ======================================
    # DATE / LEAGUE
    # ======================================

    col1, col2 = st.columns(2)


    with col1:

        edit_date = st.date_input(
            "Bet Date",
            value=datetime.strptime(
                bet["bet_date"],
                "%Y-%m-%d"
            ).date(),
            key=f"edit_date_{bet_id}"
        )


    with col2:

        edit_league = st.selectbox(
            "League",
            LEAGUES,
            index=safe_index(
                LEAGUES,
                bet["league"]
            ),
            key=f"edit_league_{bet_id}"
        )


    scope_options = [
        "PLAYER",
        "TEAM",
        "MATCH",
        "OUTRIGHT"
    ]


    edit_scope = st.radio(
        "Bet Type",
        scope_options,
        index=safe_index(
            scope_options,
            bet["scope"]
        ),
        horizontal=True,
        key=f"edit_scope_{bet_id}"
    )


    edit_event = st.text_input(
        (
            "Competition / Event"
            if edit_scope
            == "OUTRIGHT"
            else "Event"
        ),
        value=bet["event"] or "",
        key=f"edit_event_{bet_id}"
    )


    edit_subject = None
    edit_selection_2 = None
    edit_line = None
    edit_side = None


    # ======================================
    # OUTRIGHT
    # ======================================

    if edit_scope == "OUTRIGHT":

        edit_market = st.selectbox(
            "Outright Market",
            OUTRIGHT_MARKETS,
            index=safe_index(
                OUTRIGHT_MARKETS,
                bet["market"]
            ),
            key=f"edit_market_{bet_id}"
        )


        label_1, label_2 = (
            outright_selection_labels(
                edit_market
            )
        )


        edit_subject = (
            st.text_input(
                label_1,
                value=(
                    bet["subject"]
                    or ""
                ),
                key=(
                    f"edit_subject_"
                    f"{bet_id}"
                )
            )
        )


        if label_2:

            edit_selection_2 = (
                st.text_input(
                    label_2,
                    value=(
                        bet.get(
                            "selection_2"
                        )
                        or ""
                    ),
                    key=(
                        f"edit_selection2_"
                        f"{bet_id}"
                    )
                )
            )


        edit_period = (
            "Full Competition"
        )


    # ======================================
    # REGULAR
    # ======================================

    else:

        if edit_scope == "PLAYER":

            edit_subject = (
                st.text_input(
                    "Player",
                    value=(
                        bet["subject"]
                        or ""
                    ),
                    key=(
                        f"edit_player_"
                        f"{bet_id}"
                    )
                )
            )


        elif edit_scope == "TEAM":

            edit_subject = (
                st.text_input(
                    "Team",
                    value=(
                        bet["subject"]
                        or ""
                    ),
                    key=(
                        f"edit_team_"
                        f"{bet_id}"
                    )
                )
            )


        edit_market_options = (
            get_market_options(
                edit_scope
            )
        )


        edit_market = st.selectbox(
            "Market",
            edit_market_options,
            index=safe_index(
                edit_market_options,
                bet["market"]
            ),
            key=f"edit_market_{bet_id}"
        )


        edit_period = st.selectbox(
            "Period",
            PERIODS,
            index=safe_index(
                PERIODS,
                bet["period"]
            ),
            key=f"edit_period_{bet_id}"
        )


        if edit_market == "Moneyline":

            side_options = [
                "Home",
                "Away"
            ]


            edit_side = st.radio(
                "Selection",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


        elif (
            edit_market
            == "Handicap / Spread"
        ):

            side_options = [
                "Home",
                "Away"
            ]


            edit_side = st.radio(
                "Selection",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


            edit_line = (
                st.number_input(
                    "Line",
                    value=float(
                        bet["line"]
                        or 0
                    ),
                    step=0.5,
                    format="%.1f",
                    key=(
                        f"edit_line_"
                        f"{bet_id}"
                    )
                )
            )


        else:

            side_options = [
                "Over",
                "Under"
            ]


            edit_side = st.radio(
                "Side",
                side_options,
                index=safe_index(
                    side_options,
                    bet["side"]
                ),
                horizontal=True,
                key=f"edit_side_{bet_id}"
            )


            edit_line = (
                st.number_input(
                    "Line",
                    value=float(
                        bet["line"]
                        or 0
                    ),
                    step=0.5,
                    format="%.1f",
                    key=(
                        f"edit_line_"
                        f"{bet_id}"
                    )
                )
            )


    # ======================================
    # BOOK / ODDS
    # ======================================

    col1, col2 = st.columns(2)


    with col1:

        edit_bookmaker = (
            st.selectbox(
                "Bookmaker",
                BOOKMAKERS,
                index=safe_index(
                    BOOKMAKERS,
                    bet["bookmaker"]
                ),
                key=f"edit_book_{bet_id}"
            )
        )


    with col2:

        edit_market_odds = (
            st.number_input(
                "Odds Taken",
                min_value=1.01,
                value=float(
                    bet["market_odds"]
                ),
                step=0.01,
                format="%.2f",
                key=f"edit_odds_{bet_id}"
            )
        )


    # ======================================
    # ORIGIN
    # ======================================

    origin_options = [
        "SELF",
        "TIPSTER"
    ]


    edit_origin = st.radio(
        "Origin",
        origin_options,
        index=safe_index(
            origin_options,
            bet["origin"]
        ),
        horizontal=True,
        key=f"edit_origin_{bet_id}"
    )


    edit_my_odds = None
    edit_tipster_id = None
    edit_tipster_posted_odds = None
    edit_has_reasoning = False
    edit_primary = None
    edit_secondary = None


    if edit_origin == "SELF":

        edit_my_odds = (
            st.number_input(
                "My Fair Odds",
                min_value=1.01,
                value=float(
                    bet["my_odds"]
                    or 1.80
                ),
                step=0.01,
                format="%.2f",
                key=(
                    f"edit_myodds_"
                    f"{bet_id}"
                )
            )
        )


        confidence_options = [
            "Low",
            "Medium",
            "High"
        ]


        edit_confidence = (
            st.radio(
                "Confidence",
                confidence_options,
                index=safe_index(
                    confidence_options,
                    bet["confidence"],
                    1
                ),
                horizontal=True,
                key=f"edit_conf_{bet_id}"
            )
        )


        reason_options = (
            ["Select reason..."]
            + REASONS
        )


        edit_primary = (
            st.selectbox(
                "Primary Reason",
                reason_options,
                index=safe_index(
                    reason_options,
                    bet["primary_reason"]
                ),
                key=(
                    f"edit_primary_"
                    f"{bet_id}"
                )
            )
        )


        secondary_options = (
            ["None"]
            + [
                reason
                for reason in REASONS
                if reason
                != edit_primary
            ]
        )


        edit_secondary = (
            st.selectbox(
                "Secondary Reason",
                secondary_options,
                index=safe_index(
                    secondary_options,
                    (
                        bet[
                            "secondary_reason"
                        ]
                        or "None"
                    )
                ),
                key=(
                    f"edit_secondary_"
                    f"{bet_id}"
                )
            )
        )


        edit_has_reasoning = True


    else:

        tipsters = load_tipsters()


        if not tipsters:

            st.warning(
                "No tipsters saved."
            )

            edit_tipster_id = None


        else:

            tipster_names = [
                t["name"]
                for t in tipsters
            ]


            tipster_ids = {
                t["name"]:
                    t["id"]
                for t in tipsters
            }


            current_tipster = None


            for tipster in tipsters:

                if (
                    tipster["id"]
                    == bet["tipster_id"]
                ):

                    current_tipster = (
                        tipster["name"]
                    )


            selected_tipster = (
                st.selectbox(
                    "Tipster",
                    tipster_names,
                    index=safe_index(
                        tipster_names,
                        current_tipster
                    ),
                    key=(
                        f"edit_tipster_"
                        f"{bet_id}"
                    )
                )
            )


            edit_tipster_id = (
                tipster_ids[
                    selected_tipster
                ]
            )


        has_posted = (
            bet[
                "tipster_posted_odds"
            ]
            is not None
        )


        edit_has_posted = (
            st.checkbox(
                "I know the tipster's "
                "posted odds",
                value=has_posted,
                key=(
                    f"edit_hasposted_"
                    f"{bet_id}"
                )
            )
        )


        if edit_has_posted:

            edit_tipster_posted_odds = (
                st.number_input(
                    "Tipster Posted Odds",
                    min_value=1.01,
                    value=float(
                        bet[
                            "tipster_posted_odds"
                        ]
                        or 1.90
                    ),
                    step=0.01,
                    format="%.2f",
                    key=(
                        f"edit_posted_"
                        f"{bet_id}"
                    )
                )
            )


        confidence_options = [
            "N/A",
            "Low",
            "Medium",
            "High"
        ]


        edit_confidence = (
            st.radio(
                "Your Confidence",
                confidence_options,
                index=safe_index(
                    confidence_options,
                    bet["confidence"]
                ),
                horizontal=True,
                key=f"edit_conf_{bet_id}"
            )
        )


        edit_has_reasoning = (
            st.checkbox(
                "I also have my own "
                "reasoning for this bet",
                value=bool(
                    bet[
                        "has_own_reasoning"
                    ]
                ),
                key=(
                    f"edit_reasoning_"
                    f"{bet_id}"
                )
            )
        )


        if edit_has_reasoning:

            reason_options = (
                ["Select reason..."]
                + REASONS
            )


            edit_primary = (
                st.selectbox(
                    "Primary Reason",
                    reason_options,
                    index=safe_index(
                        reason_options,
                        bet[
                            "primary_reason"
                        ]
                    ),
                    key=(
                        f"edit_primary_"
                        f"{bet_id}"
                    )
                )
            )


            secondary_options = (
                ["None"]
                + [
                    reason
                    for reason in REASONS
                    if reason
                    != edit_primary
                ]
            )


            edit_secondary = (
                st.selectbox(
                    "Secondary Reason",
                    secondary_options,
                    index=safe_index(
                        secondary_options,
                        (
                            bet[
                                "secondary_reason"
                            ]
                            or "None"
                        )
                    ),
                    key=(
                        f"edit_secondary_"
                        f"{bet_id}"
                    )
                )
            )


    # ======================================
    # STAKE / RESULT
    # ======================================

    edit_stake = st.number_input(
        "Stake",
        min_value=0.01,
        value=float(
            bet["stake"]
        ),
        step=1.00,
        key=f"edit_stake_{bet_id}"
    )


    result_options = [
        "Pending",
        "Win",
        "Loss",
        "Cashout",
        "Void"
    ]


    edit_result = st.selectbox(
        "Result",
        result_options,
        index=safe_index(
            result_options,
            bet["result"]
        ),
        key=f"edit_result_{bet_id}"
    )


    edit_cashout_return = None


    if edit_result == "Cashout":

        edit_cashout_return = (
            st.number_input(
                "Cashout Return",
                min_value=0.00,
                value=float(
                    bet[
                        "cashout_return"
                    ]
                    if bet.get(
                        "cashout_return"
                    ) is not None
                    else bet["stake"]
                ),
                step=0.50,
                format="%.2f",
                key=(
                    f"edit_cashout_"
                    f"{bet_id}"
                )
            )
        )


        st.caption(
            f"Cashout P/L: "
            f"{float(edit_cashout_return) - float(edit_stake):+.2f}"
        )


    edit_notes = st.text_area(
        "Notes",
        value=bet["notes"] or "",
        key=f"edit_notes_{bet_id}"
    )


    # ======================================
    # SAVE CHANGES
    # ======================================

    if st.button(
        "💾 SAVE CHANGES",
        type="primary",
        use_container_width=True,
        key=f"save_edit_{bet_id}"
    ):


        if not edit_event.strip():

            st.error(
                "Event / Competition "
                "is required."
            )

            return


        if (
            edit_scope
            in [
                "PLAYER",
                "TEAM",
                "OUTRIGHT"
            ]
            and not (
                edit_subject
                and edit_subject.strip()
            )
        ):

            st.error(
                "Selection is required."
            )

            return


        if (
            edit_scope == "OUTRIGHT"
            and outright_needs_second_selection(
                edit_market
            )
            and not (
                edit_selection_2
                and edit_selection_2.strip()
            )
        ):

            st.error(
                "Second selection "
                "is required."
            )

            return


        if (
            edit_origin == "SELF"
            and edit_primary
            == "Select reason..."
        ):

            st.error(
                "Select a Primary Reason."
            )

            return


        if (
            edit_origin == "TIPSTER"
            and edit_tipster_id is None
        ):

            st.error(
                "Select a valid tipster."
            )

            return


        if (
            edit_origin == "TIPSTER"
            and edit_has_reasoning
            and edit_primary
            == "Select reason..."
        ):

            st.error(
                "Select a Primary Reason."
            )

            return


        metrics = calculate_metrics(
            edit_market_odds,
            edit_my_odds,
            edit_tipster_posted_odds
        )


        if edit_result == "Cashout":

            edit_profit = round(
                float(
                    edit_cashout_return
                )
                - float(edit_stake),
                2
            )

        else:

            edit_profit = (
                calculate_profit(
                    edit_result,
                    edit_stake,
                    edit_market_odds
                )
            )


        if edit_result == "Pending":

            new_settled_at = None
            new_cashout_at = None


        else:

            new_settled_at = (
                bet["settled_at"]
                or now_utc()
            )


            if (
                edit_result
                == "Cashout"
            ):

                new_cashout_at = (
                    bet.get(
                        "cashout_at"
                    )
                    or now_utc()
                )

            else:

                new_cashout_at = None


        update_record = {

            "bet_date":
                edit_date.isoformat(),

            "league":
                edit_league,

            "event":
                edit_event.strip(),

            "scope":
                edit_scope,

            "subject":
                (
                    edit_subject.strip()
                    if edit_subject
                    else None
                ),

            "selection_2":
                (
                    edit_selection_2.strip()
                    if edit_selection_2
                    else None
                ),

            "market":
                edit_market,

            "period":
                edit_period,

            "side":
                edit_side,

            "line":
                edit_line,

            "bookmaker":
                edit_bookmaker,

            "market_odds":
                edit_market_odds,

            "my_odds":
                edit_my_odds,

            "origin":
                edit_origin,

            "tipster_id":
                edit_tipster_id,

            "tipster_posted_odds":
                edit_tipster_posted_odds,

            "confidence":
                edit_confidence,

            "has_own_reasoning":
                edit_has_reasoning,

            "primary_reason":
                (
                    None
                    if edit_primary
                    == "Select reason..."
                    else edit_primary
                ),

            "secondary_reason":
                (
                    None
                    if edit_secondary
                    in [
                        None,
                        "None"
                    ]
                    else edit_secondary
                ),

            "stake":
                edit_stake,

            "result":
                edit_result,

            "settled_at":
                new_settled_at,

            "cashout_return":
                (
                    edit_cashout_return
                    if edit_result
                    == "Cashout"
                    else None
                ),

            "cashout_at":
                new_cashout_at,

            "p_market":
                metrics["p_market"],

            "p_you":
                metrics["p_you"],

            "edge_pp":
                metrics["edge_pp"],

            "ev_pct":
                metrics["ev_pct"],

            "price_deterioration_pp":
                metrics[
                    "price_deterioration_pp"
                ],

            "profit":
                edit_profit,

            "notes":
                (
                    edit_notes.strip()
                    if edit_notes.strip()
                    else None
                ),

            "updated_at":
                now_utc()
        }


        try:

            (
                supabase
                .table("bets")
                .update(
                    update_record
                )
                .eq(
                    "id",
                    bet_id
                )
                .eq(
                    "user_id",
                    st.session_state.user_id
                )
                .execute()
            )


            st.success(
                "✅ Bet updated successfully."
            )

            st.rerun()


        except Exception as e:

            st.error(
                f"Could not update bet: {e}"
            )


    # ======================================
    # SOFT DELETE
    # ======================================

    st.divider()

    st.subheader(
        "Delete Bet"
    )


    st.caption(
        "The bet will move to Trash. "
        "It will not be permanently deleted."
    )


    if (
        st.session_state.delete_confirm_id
        != bet_id
    ):

        if st.button(
            "🗑️ MOVE TO TRASH",
            use_container_width=True,
            key=f"delete_{bet_id}"
        ):

            st.session_state.delete_confirm_id = (
                bet_id
            )

            st.rerun()


    else:

        st.warning(
            "Are you sure you want "
            "to move this bet to Trash?"
        )


        c1, c2 = st.columns(2)


        with c1:

            if st.button(
                "Cancel",
                use_container_width=True,
                key=(
                    f"cancel_delete_"
                    f"{bet_id}"
                )
            ):

                st.session_state.delete_confirm_id = (
                    None
                )

                st.rerun()


        with c2:

            if st.button(
                "Yes, move to Trash",
                type="primary",
                use_container_width=True,
                key=(
                    f"confirm_delete_"
                    f"{bet_id}"
                )
            ):

                try:

                    soft_delete_bet(
                        bet_id
                    )

                    st.session_state.delete_confirm_id = (
                        None
                    )

                    st.rerun()


                except Exception as e:

                    st.error(
                        f"Could not delete "
                        f"bet: {e}"
                    )


# ==========================================
# TRASH
# ==========================================

def trash_page():

    deleted = (
        load_deleted_bets()
    )


    st.header(
        f"🗑️ Trash ({len(deleted)})"
    )


    st.caption(
        "Deleted bets are excluded from "
        "counters, History and Analysis."
    )


    if not deleted:

        st.success(
            "Trash is empty."
        )

        return


    for bet in deleted:

        st.divider()


        subject = (

            bet["event"]

            if bet["scope"] == "MATCH"

            else bet["subject"]
        )


        st.subheader(
            subject
        )


        market_text = (
            f"{bet['market']} | "
            f"{bet['side']}"
        )


        if bet["line"] is not None:

            market_text += (
                f" {float(bet['line']):g}"
            )


        st.write(
            market_text
        )


        st.caption(
            f"{bet['league']} | "
            f"Odds {float(bet['market_odds']):.2f} | "
            f"Result: {bet['result']}"
        )


        st.caption(
            f"Deleted: "
            f"{bet['deleted_at'] or 'Unknown'}"
        )


        if st.button(
            "♻️ RESTORE",
            key=f"restore_{bet['id']}",
            use_container_width=True
        ):

            try:

                restore_bet(
                    bet["id"]
                )

                st.rerun()


            except Exception as e:

                st.error(
                    f"Could not restore bet: {e}"
                )


# ==========================================
# MAIN
# ==========================================

if not st.session_state.logged_in:

    login_page()

    st.stop()


# ==========================================
# SIDEBAR
# ==========================================

with st.sidebar:

    st.write(
        f"👤 "
        f"{st.session_state.user_email}"
    )


    if st.button(
        "Logout",
        use_container_width=True
    ):

        logout()


# ==========================================
# HEADER
# ==========================================

st.title(
    "🏀 Bet Tracker"
)

st.caption(
    "Personal basketball betting tracker"
)


# ==========================================
# COUNTERS
# ==========================================

try:

    total_bets = (
        get_total_bets_count()
    )

    pending_count = (
        get_pending_bets_count()
    )

    settled_count = (
        get_settled_bets_count()
    )


    c1, c2, c3 = st.columns(3)


    with c1:

        st.metric(
            "Total Bets",
            total_bets
        )


    with c2:

        st.metric(
            "Pending",
            pending_count
        )


    with c3:

        st.metric(
            "Settled",
            settled_count
        )


except Exception as e:

    st.warning(
        f"Could not load counters: {e}"
    )



# ==========================================
# NAVIGATION
# ==========================================

(
    add_tab,
    pending_tab,
    history_tab,
    analysis_tab,
    suggestions_tab,
    manage_tab,
    trash_tab
) = st.tabs([

    "➕ Add Bet",
    "⏳ Pending",
    "📜 History",
    "📊 Analysis",
    "💡 Suggestions",
    "✏️ Manage",
    "🗑️ Trash"
])


with add_tab:

    add_bet_page()


with pending_tab:

    pending_bets_page()


with history_tab:

    history_page()


with analysis_tab:

    analysis_page(
        supabase,
        load_tipsters
    )


with suggestions_tab:

    suggestions_page(
        supabase,
        load_tipsters
    )


with manage_tab:

    manage_bets_page()


with trash_tab:

    trash_page()
