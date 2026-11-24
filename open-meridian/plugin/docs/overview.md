# Overview

A read-only trading desk on this deployment: panels a person docks, tabs and
floats, built with Dockview's MIT packages, with OpenAlgo Charts for the price
chart. The plugin reads through its sidecar, at its own scope, and shows each
person only the rows of the accounts they may read on it.

## What it reads

- Orders, placements and fills in the book, newest first, kept current by
  reading what changed since the last read.
- Positions in the book.
- The latest price of the instrument picked, with its time and dataset.
- Bars of that instrument, at each bar length the lake holds.
- An instrument in the deployment's master, by an identifier.

Each of these reads is also a read tool an agent calls for a person, under
the same levels and cut to the same accounts.

## What it does not do

- It places, amends, cancels and releases nothing: no button or chart hook
  sends an order.
- It keeps nothing. A layout lasts while the page is open.
- It has no sign-in of its own: the deployment signs people in and holds
  their access.
- It calls no address outside the deployment.
