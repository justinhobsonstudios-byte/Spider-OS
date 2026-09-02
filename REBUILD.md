# Controlled installer rebuild

This branch starts from main commit `43d0e5bd098f6317ade6027896339321e317493a`.

## Milestone 1 gate

The production ISO must:

1. boot the real Anaconda runtime;
2. install the embedded bootc payload to a blank virtual disk;
3. reboot with the ISO removed;
4. reach `graphical.target`;
5. run Aurora's `plasmalogin.service`; and
6. expose a Plasma Wayland session.

Spider services, the health endpoint, Webbie, and Web Assembly are intentionally
outside this gate. They will be restored one layer at a time only after this gate
is green.
