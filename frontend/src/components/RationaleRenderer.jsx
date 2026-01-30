import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import { Box } from '@mui/material';

const RationaleRenderer = ({ content }) => {
    return (
        <Box sx={{
            '& span': { display: 'inline' },
            '& strong': {
                color: 'primary.main', // Use theme primary (Cyan in dark, blue in light)
                fontWeight: 900,
                textShadow: (theme) => theme.palette.mode === 'dark' ? '0 0 10px rgba(0, 229, 255, 0.2)' : 'none'
            },
            '& ul': { pl: 2, m: 0 },
            '& li': { mb: 0.75, color: 'text.primary' },
            '& p': { mb: 1.5, '&:last-child': { mb: 0 }, lineHeight: 1.8, color: 'text.primary' }
        }}>
            <ReactMarkdown rehypePlugins={[rehypeRaw]}>
                {content}
            </ReactMarkdown>
        </Box>
    );
};

export default RationaleRenderer;
