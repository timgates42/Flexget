from __future__ import unicode_literals, division, absolute_import
import logging
import posixpath
from fnmatch import fnmatch
from flexget.plugin import register_plugin, priority

log = logging.getLogger('content_filter')


class FilterContentFilter(object):
    """
    Rejects entries based on the filenames in the content. Torrent files only right now.

    Example::

      content_filter:
        require:
          - '*.avi'
          - '*.mkv'
    """

    schema = {
        'type': 'object',
        'properties': {
            'require': {'$ref': '#/definitions/string_or_strings'},
            'reject': {'$ref': '#/definitions/string_or_strings'},
            'strict': {'type': 'boolean'}
        },
        'additionalProperties': False,
        'definitions': {
            'string_or_strings': {
                'anyOf': [
                    {'type': 'string'},
                    {'type': 'array', 'items': {'type': 'string'}}
                ]
            }
        }
    }

    def get_config(self, task):
        config = task.config.get('content_filter')
        for key in ['require', 'reject']:
            if key in config:
                if isinstance(config[key], basestring):
                    config[key] = [config[key]]
        return config

    def process_entry(self, task, entry):
        """
        Process an entry and reject it if it doesn't pass filter.

        :param task: Task entry belongs to.
        :param entry: Entry to process
        :return: True, if entry was rejected.
        """
        config = self.get_config(task)
        if 'content_files' in entry:
            files = entry['content_files']
            log.debug('%s files: %s' % (entry['title'], files))

            def matching_mask(files, masks):
                """Returns matching mask if any files match any of the masks, false otherwise"""
                for file in files:
                    for mask in masks:
                        if fnmatch(file, mask):
                            return mask
                return False

            # Avoid confusion by printing a reject message to info log, as
            # download plugin has already printed a downloading message.
            if config.get('require'):
                if not matching_mask(files, config['require']):
                    log.info('Entry %s does not have any of the required filetypes, rejecting' % entry['title'])
                    entry.reject('does not have any of the required filetypes', remember=True)
                    return True
            if config.get('reject'):
                mask = matching_mask(files, config['reject'])
                if mask:
                    log.info('Entry %s has banned file %s, rejecting' % (entry['title'], mask))
                    entry.reject('has banned file %s' % mask, remember=True)
                    return True

    def parse_torrent_files(self, entry):
        if 'torrent' in entry:
            files = [posixpath.join(item['path'], item['name']) for item in entry['torrent'].get_filelist()]
            if files:
                entry['content_files'] = files

    @priority(150)
    def on_task_modify(self, task):
        if task.manager.options.test or task.manager.options.learn:
            log.info('Plugin is partially disabled with --test and --learn because content filename information may not be available')
            #return

        config = self.get_config(task)
        for entry in task.accepted:
            # TODO: I don't know if we can pares filenames from nzbs, just do torrents for now
            # possibly also do compressed files in the future
            self.parse_torrent_files(entry)
            if self.process_entry(task, entry):
                task.rerun()
            elif not 'content_files' in entry and config.get('strict'):
                entry.reject('no content files parsed for entry', remember=True)
                task.rerun()

register_plugin(FilterContentFilter, 'content_filter')
