# Invoice totals

## Purpose

Help an accounts team turn its invoice CSV export into a compact totals report, so it can reconcile invoices without manually adding amounts in a spreadsheet.

## Existing input

The CSV export has `invoice_id`, `customer`, `currency` and `amount` columns. Invoice IDs and customer names are strings. Amounts may be positive invoices or negative credit notes. The existing amount parser supports finite decimal amounts in whole cents and rejects fractional cents rather than rounding them.

## Current state

Header and amount parsing helpers are implemented and tested. The CLI is an empty entry point; totals and report output are not implemented.

## Decisions still needed

The business owner must settle the totals grouping, handling of different currencies and repeated invoice IDs, output format, and what a user sees when an input row is invalid. These decisions determine the acceptance examples.

## Constraints

Keep this an offline Python command using the standard library. All repository data is synthetic. No release or distribution form has been chosen; the project currently runs from its checkout.
