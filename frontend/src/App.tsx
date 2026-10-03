import { Button, Flex, Typography } from 'antd'

const { Title, Paragraph } = Typography

const App = () => (
  <Flex vertical align="center" justify="center" gap="middle" className="app-shell">
    <Title>Catlity QMS</Title>
    <Paragraph type="secondary">Quality management and audit platform</Paragraph>
    <Button type="primary">Get started</Button>
  </Flex>
)

export default App
