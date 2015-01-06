======
hgtool
======

hgtool allows to do safe operations with hg.

Usage
=====

hgtool [-p|--props-file] [-r|--rev revision] [-b|--branch branch]
       [-s|--shared-dir shared_dir] [--check-outgoing] repo [dest]

Caveat
======
revision/branch on commandline will override those in props-file
