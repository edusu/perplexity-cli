"""CLI commands for Perplexity Finance."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import click
from rich.table import Table

from perplexity.cli.helpers import authenticated_client, console, get_storage_from_ctx, run_async


def _color_pct(pct: float) -> str:
    """Format a percent value with a green/red Rich color tag based on sign."""
    sign = "+" if pct >= 0 else ""
    color = "green" if pct >= 0 else "red"
    return f"[{color}]{sign}{pct:.2f}%[/{color}]"


def _color_change(change: float, currency: str = "USD") -> str:
    """Format an absolute change with a green/red Rich color tag."""
    sign = "+" if change >= 0 else ""
    color = "green" if change >= 0 else "red"
    return f"[{color}]{sign}{change:.2f} {currency}[/{color}]"


def _dump_json(obj: Any) -> None:
    """Print any dataclass (or list/dict of dataclasses) as indented JSON."""
    data: Any
    if isinstance(obj, list):
        data = [asdict(x) if hasattr(x, "__dataclass_fields__") else x for x in obj]
    elif hasattr(obj, "__dataclass_fields__"):
        data = asdict(obj)
    else:
        data = obj
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _render_movers_table(title: str, items: list) -> Table:
    """Build a Rich Table for a list of Mover/Index/Sector dataclasses."""
    table = Table(title=title, show_header=True)
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Name")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("%", justify="right")
    for m in items:
        pct_str = _color_pct(m.change_percent)
        ch_str = _color_change(m.change, getattr(m, "currency", "USD"))
        table.add_row(m.symbol, m.name, f"{m.price:.2f}", ch_str, pct_str)
    return table


@click.group()
def finance() -> None:
    """Perplexity Finance — quotes, market data, news, predictions."""


# ---------------- Ticker commands ----------------


@finance.command()
@click.argument("ticker")
@click.option("--history", is_flag=True, help="Include intraday price history.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def quote(ctx: click.Context, ticker: str, history: bool, as_json: bool) -> None:
    """Get the current price quote for a ticker (stock, crypto, index, ETF)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        q = await client.finance.quote(ticker, with_history=history)

    if as_json:
        _dump_json(q)
        return

    console.print(f"[bold cyan]{q.symbol}[/bold cyan] — {q.name}  [dim]({q.exchange})[/dim]")
    console.print(
        f"  Price: [bold]{q.price:.2f} {q.currency}[/bold]   "
        f"Change: {_color_change(q.change, q.currency)}   "
        f"Pct: {_color_pct(q.change_percent)}"
    )
    if q.market_cap:
        console.print(f"  Market cap: {q.market_cap:,.0f} {q.currency}")
    if q.day_low and q.day_high:
        console.print(f"  Day range: {q.day_low:.2f}–{q.day_high:.2f}")
    if q.year_low and q.year_high:
        console.print(f"  52-week range: {q.year_low:.2f}–{q.year_high:.2f}")
    if q.pe is not None:
        console.print(f"  PE: {q.pe:.2f}   EPS: {q.eps or 0:.2f}")
    if q.after_hours_price is not None:
        console.print(
            f"  After-hours: {q.after_hours_price:.2f} "
            f"({_color_pct(q.after_hours_percent_change or 0)})"
        )
    if history and q.history:
        console.print(f"  History points: {len(q.history)}")


@finance.command()
@click.argument("ticker")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def profile(ctx: click.Context, ticker: str, as_json: bool) -> None:
    """Show the company profile for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        p = await client.finance.profile(ticker)

    if as_json:
        _dump_json(p)
        return

    console.print(f"[bold cyan]{p.symbol}[/bold cyan] — {p.company_name}")
    console.print(f"  Exchange: {p.exchange}   Industry: {p.industry}")
    if p.website:
        console.print(f"  Website: {p.website}")
    console.print()
    console.print(p.description)


@finance.command()
@click.argument("ticker")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def why(ctx: click.Context, ticker: str, as_json: bool) -> None:
    """Explain why a ticker moved today (AI-generated with sources)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        m = await client.finance.why_moving(ticker)

    if as_json:
        _dump_json(m)
        return

    console.print(f"[bold cyan]{ticker.upper()}[/bold cyan]: {m.explanation}")
    if m.sources:
        console.print("\n[bold]Sources:[/bold]")
        for i, s in enumerate(m.sources, 1):
            console.print(f"  [{i}] {s.name} — {s.url}")


@finance.command()
@click.argument("ticker")
@click.option("--limit", default=10, show_default=True, help="Max articles to return.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def news(ctx: click.Context, ticker: str, limit: int, as_json: bool) -> None:
    """Show publisher news for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.ticker_news(ticker, limit=limit)

    if as_json:
        _dump_json(items)
        return

    if not items:
        console.print(f"[yellow]No news for {ticker.upper()}.[/yellow]")
        return
    for n in items:
        console.print(f"[bold]{n.title}[/bold]")
        if n.publisher:
            console.print(f"  [dim]{n.publisher}[/dim]")
        console.print(f"  {n.url}\n")


@finance.command()
@click.argument("ticker")
@click.option("--limit", default=20, show_default=True, help="Max timeline entries.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def timeline(ctx: click.Context, ticker: str, limit: int, as_json: bool) -> None:
    """Show the narrative news timeline for a ticker."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        entries = await client.finance.timeline(ticker, limit=limit)

    if as_json:
        _dump_json(entries)
        return

    if not entries:
        console.print(f"[yellow]No timeline entries for {ticker.upper()}.[/yellow]")
        return
    for e in entries:
        console.print(f"[bold]{e.last_modified}[/bold] — {e.ticker}")
        console.print(f"  {e.description}")
        if e.source_urls:
            console.print(f"  [dim]Sources: {len(e.source_urls)}[/dim]")
        console.print()


# ---------------- Market commands ----------------


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def market(ctx: click.Context, country: str, as_json: bool) -> None:
    """Show a combined market overview (summary + indices + movers)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        summary_items = await client.finance.market_summary(country=country)
        idx = await client.finance.indices(country=country)
        mvs = await client.finance.movers(country=country)

    if as_json:
        _dump_json(
            {
                "summary": [asdict(s) for s in summary_items],
                "indices": [asdict(i) for i in idx],
                "movers": [asdict(m) for m in mvs],
            }
        )
        return

    if summary_items:
        console.print("[bold underline]Market headlines[/bold underline]")
        for s in summary_items:
            console.print(f"• [bold]{s.header}[/bold]")
            console.print(f"  {s.detail}")
        console.print()
    if idx:
        console.print(_render_movers_table("Indices", idx))
    if mvs:
        console.print(_render_movers_table("Top movers", mvs))


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def movers(ctx: click.Context, country: str, as_json: bool) -> None:
    """Show today's top market movers."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.movers(country=country)

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No movers found.[/yellow]")
        return
    console.print(_render_movers_table("Top movers", items))


@finance.command()
@click.option(
    "--market",
    "market_kind",
    type=click.Choice(["stocks", "crypto"]),
    default="stocks",
    show_default=True,
)
@click.option("--country", default="US", show_default=True)
@click.option("--history", is_flag=True, help="Include intraday history.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def indices(
    ctx: click.Context,
    market_kind: str,
    country: str,
    history: bool,
    as_json: bool,
) -> None:
    """Show major indices (stocks or crypto)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.indices(
            market=market_kind, country=country, with_history=history
        )

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No indices returned.[/yellow]")
        return
    console.print(_render_movers_table(f"Indices ({market_kind})", items))


@finance.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def sectors(ctx: click.Context, as_json: bool) -> None:
    """Show sector ETFs."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.sectors()

    if as_json:
        _dump_json(items)
        return
    console.print(_render_movers_table("Sectors", items))


@finance.command(name="fixed-income")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def fixed_income(ctx: click.Context, as_json: bool) -> None:
    """Show fixed-income instruments (bonds, yields)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.fixed_income()

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print("[yellow]No fixed income data.[/yellow]")
        return
    for fi in items:
        console.print(
            f"[bold cyan]{fi.symbol}[/bold cyan] {fi.name}  "
            f"{fi.price:.2f}  {_color_pct(fi.change_percent)}"
        )


# ---------------- Predictions / personal ----------------


@finance.command()
@click.option(
    "--tag",
    type=click.Choice(["finance", "crypto", "politics", "earnings"]),
    default="finance",
    show_default=True,
)
@click.option("--limit", default=10, show_default=True)
@click.option("--commentary", is_flag=True, help="Include AI commentary.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def predictions(
    ctx: click.Context, tag: str, limit: int, commentary: bool, as_json: bool
) -> None:
    """Show prediction markets (Polymarket-backed) by tag."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        items = await client.finance.predictions(tag=tag, limit=limit, commentary=commentary)

    if as_json:
        _dump_json(items)
        return
    if not items:
        console.print(f"[yellow]No prediction markets for tag '{tag}'.[/yellow]")
        return
    for pm in items:
        console.print(f"[bold]{pm.title}[/bold]  [dim]({pm.provider}, vol={pm.volume:,.0f})[/dim]")
        for opt in pm.markets[:5]:
            pct = opt.probability * 100
            console.print(f"  • {opt.question}: [bold]{pct:.1f}%[/bold]")
        console.print()


@finance.command()
@click.option("--country", default="US", show_default=True)
@click.option("--with-quotes", is_flag=True, help="Also fetch live quotes.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def watchlist(ctx: click.Context, country: str, with_quotes: bool, as_json: bool) -> None:
    """Show the user's saved watchlist."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        wl = await client.finance.watchlist(country=country)
        quotes: list | None = None
        if with_quotes:
            quotes = await client.finance.watchlist_quotes(country=country)

    if as_json:
        payload: dict[str, Any] = {"symbols": wl.symbols}
        if quotes:
            payload["quotes"] = [asdict(q) for q in quotes]
        _dump_json(payload)
        return

    if not wl.symbols:
        console.print("[yellow]Watchlist is empty.[/yellow]")
        return
    if quotes:
        console.print(_render_movers_table("Watchlist", quotes))
    else:
        console.print("[bold]Watchlist:[/bold] " + ", ".join(wl.symbols))


@finance.command()
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def portfolio(ctx: click.Context, as_json: bool) -> None:
    """Show the Plaid-linked portfolio overview."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        overview = await client.finance.portfolio_overview()

    if as_json:
        _dump_json(overview if overview else {})
        return

    if overview is None:
        console.print("[yellow]No portfolio linked. Connect via the Perplexity web UI.[/yellow]")
        return
    console.print(f"[bold]Total value:[/bold] {overview.total_value:,.2f}")
    console.print(
        f"[bold]Day change:[/bold] "
        f"{_color_change(overview.day_change)} "
        f"({_color_pct(overview.day_change_percent)})"
    )
    console.print(f"[bold]Accounts:[/bold] {len(overview.accounts)}")


@finance.command()
@click.argument("query")
@click.option("--country", default="US", show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
@click.pass_context
@run_async
async def search(ctx: click.Context, query: str, country: str, as_json: bool) -> None:
    """Search for tickers by name (autosuggest)."""
    async with authenticated_client(get_storage_from_ctx(ctx)) as client:
        hits = await client.finance.autosuggest(query, country=country)

    if as_json:
        _dump_json(hits)
        return
    if not hits:
        console.print(f"[yellow]No matches for '{query}'.[/yellow]")
        return
    for h in hits:
        console.print(f"[bold cyan]{h.symbol}[/bold cyan]  {h.name}  [dim]({h.kind})[/dim]")
