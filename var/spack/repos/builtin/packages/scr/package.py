# Copyright 2013-2021 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import sys

from spack import *


def detect_scheduler():
    if which('aprun'):
        return 'APRUN'
    if which('jsrun'):
        return 'LSF'
    return 'SLURM'


class Scr(CMakePackage):
    """SCR caches checkpoint data in storage on the compute nodes of a
       Linux cluster to provide a fast, scalable checkpoint/restart
       capability for MPI codes"""

    homepage = "https://computing.llnl.gov/projects/scalable-checkpoint-restart-for-mpi"
    url      = "https://github.com/LLNL/scr/archive/v1.2.0.tar.gz"
    git      = "https://github.com/llnl/scr.git"
    tags     = ['radiuss']

    tags = ['e4s']

    version('develop', branch='develop')
    version('legacy', branch='legacy', deprecated=True)

    version('3.0rc1', sha256='bd31548a986f050024429d8ee3644eb135f047f98a3d503a40c5bd4a85291308')
    version('2.0.0', sha256='471978ae0afb56a20847d3989b994fbd680d1dea21e77a5a46a964b6e3deed6b', deprecated=True)
    version('1.2.2', sha256='764a85638a9e8762667ec1f39fa5f7da7496fca78de379a22198607b3e027847', deprecated=True)
    version('1.2.1', sha256='23acab2dc7203e9514455a5168f2fd57bc590affb7a1876912b58201513628fe', deprecated=True)
    version('1.2.0', sha256='e3338ab2fa6e9332d2326c59092b584949a083a876adf5a19d4d5c7a1bbae047', deprecated=True)

    depends_on('pdsh+static_modules', type=('build', 'run'))
    depends_on('zlib')
    depends_on('mpi')

    # Use the latest iteration of the components when installing scr@develop
    depends_on('axl@main',      when="@develop")
    depends_on('er@main',       when="@develop")
    depends_on('kvtree@main',   when="@develop")
    depends_on('rankstr@main',  when="@develop")
    depends_on('redset@main',   when="@develop")
    depends_on('shuffile@main', when="@develop")
    depends_on('spath@main',    when="@develop")

    # SCR legacy is anything 2.x.x or earlier
    # SCR components is anything 3.x.x or later
    depends_on('axl@0.4.0:',      when="@3:")
    depends_on('er@0.0.4:',       when="@3:")
    depends_on('kvtree@1.1.1:',   when="@3:")
    depends_on('rankstr@0.0.3:',  when="@3:")
    depends_on('redset@0.0.5:',   when="@3:")
    depends_on('shuffile@0.0.4:', when="@3:")
    depends_on('spath@0.0.2:',    when="@3:")

    # DTCMP is an optional dependency up until 3.x
    variant('dtcmp', default=True,
            description="Build with DTCMP. "
            "Necessary to enable user directory naming at runtime")
    depends_on('dtcmp', when="@:2 +dtcmp")

    # DTCMP is a required dependency with 3.x and later
    conflicts('~dtcmp', when="@3:", msg="<SCR> DTCMP required for versions >=3")
    depends_on('dtcmp', when="@3:")

    variant('libyogrt', default=True,
            description="Build SCR with libyogrt for get_time_remaining.")
    depends_on('libyogrt scheduler=slurm', when="+libyogrt resource_manager=SLURM")
    depends_on('libyogrt scheduler=lsf', when="+libyogrt resource_manager=LSF")
    depends_on('libyogrt', when="+libyogrt")

    # Enabling SCR logging is a WIP, for which this will be needed
    # variant('mysql', default=True, decription="MySQL database for logging")
    # depends_on('mysql', when="+mysql")

    variant('scr_config', default='scr.conf',
            description='Location for SCR to find its system config file. '
            'May be either absolute or relative to the install prefix')
    variant('copy_config', default='none',
            description='Location from which to copy SCR system config file. '
            'Must be an absolute path.')

    variant('fortran', default=True,
            description="Build SCR with fortran bindings")

    variant('resource_manager', default=detect_scheduler(),
            values=('SLURM', 'APRUN', 'PMIX', 'LSF', 'NONE'),
            multi=False,
            description="Resource manager for which to configure SCR.")

    # SCR_ASYNC_API in process of being automated. Only applying this to :2.x.x
    variant('async_api', default='NONE',
            values=('NONE', 'CRAY_DW', 'IBM_BBAPI', 'INTEL_CPPR'),
            multi=False,
            description="Asynchronous data transfer API to use with SCR.")

    variant('bbapi_fallback', default='False',
            description='Using BBAPI, if source or destination don\'t support \
            file extents then fallback to pthreads')
    depends_on('axl+bbapi_fallback', when="@3: +bbapi_fallback")

    variant('file_lock', default='FLOCK',
            values=('FLOCK', 'FNCTL', 'NONE'),
            multi=False,
            description='File locking style for SCR.')
    depends_on('kvtree file_lock=FLOCK', when='@3: file_lock=FLOCK')
    depends_on('kvtree file_lock=FNCTL', when='@3: file_lock=FNCTL')
    depends_on('kvtree file_lock=NONE',  when='@3: file_lock=NONE')

    # The default cache and control directories should be placed in tmpfs if available.
    # On Linux, /dev/shm is a common tmpfs location.  Other platforms, like macOS,
    # do not define a common tmpfs location, so /tmp is the next best option.
    platform_tmp_default = '/dev/shm' if sys.platform == 'linux' else '/tmp'
    variant('cache_base', default=platform_tmp_default,
            description='Compile time default location for cache directory.')
    variant('cntl_base', default=platform_tmp_default,
            description='Compile time default location for control directory.')

    def flag_handler(self, name, flags):
        if self.spec.satisfies('%cce'):
            if name in ['cflags', 'cxxflags', 'cppflags']:
                return (None, flags, None)
            elif name == 'ldflags':
                flags.append('-ldl')
        return (flags, None, None)

    def get_abs_path_rel_prefix(self, path):
        # Return path if absolute, otherwise prepend prefix
        if os.path.isabs(path):
            return path
        else:
            return join_path(self.spec.prefix, path)

    def cmake_args(self):
        spec = self.spec
        args = []

        if 'platform=cray' in spec:
            args.append('-DSCR_LINK_STATIC=OFF')

        args.append('-DENABLE_FORTRAN={0}'.format('+fortran' in spec))

        conf_path = self.get_abs_path_rel_prefix(
            self.spec.variants['scr_config'].value)
        args.append('-DSCR_CONFIG_FILE={0}'.format(conf_path))

        # We uppercase the values for these to avoid unnecessary user error.
        args.append('-DSCR_RESOURCE_MANAGER={0}'.format(
            spec.variants['resource_manager'].value.upper()))

        if spec.satisfies('@:2'):
            args.append('-DSCR_ASYNC_API={0}'.format(
                spec.variants['async_api'].value.upper()))

        args.append('-DSCR_FILE_LOCK={0}'.format(
            spec.variants['file_lock'].value.upper()))

        args.append('-DSCR_CACHE_BASE={0}'.format(
            spec.variants['cache_base'].value))

        args.append('-DSCR_CNTL_BASE={0}'.format(
            spec.variants['cntl_base'].value))

        args.append('-DWITH_PDSH_PREFIX={0}'.format(spec['pdsh'].prefix))

        if "+dtcmp" in spec:
            args.append('-DWITH_DTCMP_PREFIX={0}'.format(spec['dtcmp'].prefix))

        if "+libyogrt" in spec:
            args.append('-DWITH_YOGRT_PREFIX={0}'.format(
                spec['libyogrt'].prefix))

        # if "+mysql" in spec:
        # args.append('-DWITH_MYSQL_PREFIX={0}'.format(
        # spec['mysql'].prefix))

        return args

    @run_after('install')
    def copy_config(self):
        spec = self.spec
        if spec.variants['copy_config'].value != 'none':
            dest_path = self.get_abs_path_rel_prefix(
                spec.variants['scr_config'].value)
            install(spec.variants['copy_config'].value, dest_path)
