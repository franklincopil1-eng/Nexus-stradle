# Security Specification: Atlas-X Trading Engine

## Data Invariants
- Only authenticated users can read or write data.
- The `system/state` singleton must only be updated with valid `TradingState` objects.
- Commands must be processed and then deleted (or marked as processed).
- Logs are append-only for the system and read-only for the user.

## The Dirty Dozen Payloads
1. **Unauthenticated Read**: Attempting to read `/system/state` without a token.
2. **Unauthenticated Write**: Attempting to set `/system/state` without a token.
3. **Invalid Status**: Setting `systemStatus` to "EXPLODED" (not in enum).
4. **Price Poisoning**: Setting `price` to a 2MB string.
5. **Log Spoofing**: Attempting to overwrite an existing log entry.
6. **Command Injection**: Adding a field `unauthorizedCode` to a command document.
7. **Size Attack**: Creating an order with a `ticket` string of 1MB.
8. **Negative Account**: Setting `account.balance` to a negative number if the app doesn't allow it (though margin can be negative, balance usually isn't unless debt).
9. **Duplicate State**: Attempting to create a second document in `/system/` that isn't `state`.
10. **Admin Elevation**: Attempting to write to a hypothetical `admins` collection.
11. **Type Mismatch**: Setting `spread` to a boolean.
12. **Future Heartbeat**: Setting `lastHeartbeat` to a time 10 years in the future.

## Test Runner Logic
The `firestore.rules.test.ts` (conceptual) will ensure that all above scenarios (1, 2, 3, 4, 11) are rejected by the rules. We will implement strict schema validation in the rules.
