param(
    [Parameter(Mandatory=$true)]
    [string]$Root
)

$ErrorActionPreference = "Stop"

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path)
}

function Write-Utf8([string]$Path, [string]$Content) {
    [System.IO.File]::WriteAllText($Path, $Content, [System.Text.UTF8Encoding]::new($false))
}

function Replace-Literal([string]$Path, [string]$Old, [string]$New) {
    $text = Read-Utf8 $Path
    if (-not $text.Contains($Old)) {
        throw "Trecho esperado nao encontrado em $Path"
    }
    Write-Utf8 $Path ($text.Replace($Old, $New))
}

$vm = Join-Path $Root "YoutubeApp/ViewModels/AddLinkWindowViewModel.cs"
$text = Read-Utf8 $vm

$text = $text.Replace(
'    private const string VideoPattern =',
'    private const int MaxLinks = 100;

    private const string VideoPattern ='
)

$needle = @'
        if (CurrentPage == 0)
        {
            var videos = new Dictionary<string, bool>();
'@
$replacement = @'
        if (CurrentPage == 0)
        {
            var nonEmptyLinks = Links
                .Split(new string[] { "\r\n", "\r", "\n" }, StringSplitOptions.None)
                .Select(x => x.Trim())
                .Where(x => x.Length > 0)
                .ToList();

            if (nonEmptyLinks.Count > MaxLinks)
            {
                await _messenger.Send(new ShowMessageBoxMessage
                {
                    Title = "Limite de links",
                    Message = $"Cole no maximo {MaxLinks} links por vez. Foram encontrados {nonEmptyLinks.Count}.",
                    Icon = Icon.Warning,
                    ButtonDefinitions = ButtonEnum.Ok
                }, (int)MessengerChannel.AddLinkWindow);
                return;
            }

            var videos = new Dictionary<string, bool>();
'@
if (-not $text.Contains($needle)) { throw "Nao foi possivel inserir o limite de 100 links." }
$text = $text.Replace($needle, $replacement)

$text = $text.Replace(
'        $"{_videos.Count + _addedVideoCount} Video(s) + {_playlists.Count + _addedPlaylistCount} Playlist(s)";',
'        $"{_videos.Count + _addedVideoCount} video(s) + {_playlists.Count + _addedPlaylistCount} playlist(s)";'
)
$text = $text.Replace('Title = "Error", Message = $"Invalid link at line {error.LineNumber}:\n{error.Text}"',
                      'Title = "Link invalido", Message = $"Link invalido na linha {error.LineNumber}:\n{error.Text}"')
$text = $text.Replace('Title = "Error", Message = e.Message', 'Title = "Erro", Message = e.Message')
$text = $text.Replace('Title = "Save To...",', 'Title = "Escolher pasta de destino",')
Write-Utf8 $vm $text

$addLinkView = @'
<Window xmlns="https://github.com/avaloniaui"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        xmlns:d="http://schemas.microsoft.com/expression/blend/2008"
        xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
        xmlns:local="clr-namespace:YoutubeApp"
        xmlns:vm="using:YoutubeApp.ViewModels"
        mc:Ignorable="d" d:DesignWidth="760" d:DesignHeight="500"
        MinWidth="720" MinHeight="430"
        Width="760" Height="500"
        x:Class="YoutubeApp.Views.AddLinkWindow"
        x:DataType="vm:AddLinkWindowViewModel"
        x:CompileBindings="True"
        d:DataContext="{x:Static local:DesignViewModels.AddLinkWindow}"
        Title="Adicionar videos e playlists"
        Icon="/Assets/app-logo.ico"
        WindowStartupLocation="CenterOwner"
        Background="#0F172A">

    <Grid Margin="22" RowDefinitions="Auto,18,*,18,Auto">
        <StackPanel Grid.Row="0" Spacing="5">
            <TextBlock Text="Adicionar downloads" FontSize="25" FontWeight="SemiBold" Foreground="White"/>
            <TextBlock Text="Cole ate 100 links do YouTube, um por linha. Links de playlist continuam aceitos."
                       FontSize="14" Foreground="#CBD5E1"/>
        </StackPanel>

        <Border Grid.Row="2" CornerRadius="14" Background="#172033" Padding="18">
            <Panel>
                <Grid RowDefinitions="*,14,Auto,8,Auto" IsVisible="{Binding !CurrentPage}">
                    <TextBox Grid.Row="0"
                             Name="Links"
                             Text="{Binding Links}"
                             Watermark="Cole aqui videos e playlists (maximo 100 links)"
                             AcceptsReturn="True"
                             TextWrapping="Wrap"
                             FontSize="14"/>
                    <TextBlock Grid.Row="2" Text="Pasta de destino" FontWeight="SemiBold" Foreground="#E2E8F0"/>
                    <Grid Grid.Row="4" ColumnDefinitions="*,Auto">
                        <TextBox Grid.Column="0" Text="{Binding SaveTo}"/>
                        <Button Grid.Column="1"
                                Command="{Binding BrowseButtonPressedCommand}"
                                ToolTip.Tip="Escolher pasta"
                                Margin="8 0 0 0"
                                Padding="12 7">
                            <TextBlock Text="Procurar"/>
                        </Button>
                    </Grid>
                </Grid>

                <Grid RowDefinitions="Auto,12,*" IsVisible="{Binding CurrentPage}">
                    <TextBlock Grid.Row="0"
                               Text="{Binding Stats}"
                               FontSize="19"
                               FontWeight="SemiBold"
                               Foreground="White"
                               HorizontalAlignment="Center"/>
                    <ScrollViewer Grid.Row="2" VerticalScrollBarVisibility="Visible">
                        <ItemsControl ItemsSource="{Binding VideosWithPlaylist}"
                                      Grid.IsSharedSizeScope="True"
                                      HorizontalAlignment="Center">
                            <ItemsControl.ItemTemplate>
                                <DataTemplate>
                                    <StackPanel>
                                        <ItemsControl ItemsSource="{Binding VideoIds}">
                                            <ItemsControl.ItemTemplate>
                                                <DataTemplate>
                                                    <Grid ColumnDefinitions="*,12,*" Margin="4">
                                                        <RadioButton Grid.Column="0"
                                                                     IsChecked="{Binding $parent[ItemsControl].((vm:VideoWithPlaylist)DataContext).VideoIsSelected}"
                                                                     Content="{Binding ., StringFormat=Video ({0})}"
                                                                     Command="{Binding $parent[Window].((vm:AddLinkWindowViewModel)DataContext).RadioButtonClickedCommand}"
                                                                     Margin="8"/>
                                                        <RadioButton Grid.Column="2"
                                                                     IsChecked="{Binding $parent[ItemsControl].((vm:VideoWithPlaylist)DataContext).PlaylistIsSelected}"
                                                                     Content="{Binding $parent[ItemsControl].((vm:VideoWithPlaylist)DataContext).PlaylistId, StringFormat=Playlist ({0})}"
                                                                     Command="{Binding $parent[Window].((vm:AddLinkWindowViewModel)DataContext).RadioButtonClickedCommand}"
                                                                     Margin="8"/>
                                                    </Grid>
                                                </DataTemplate>
                                            </ItemsControl.ItemTemplate>
                                        </ItemsControl>
                                        <Rectangle Fill="#334155" Height="1"/>
                                    </StackPanel>
                                </DataTemplate>
                            </ItemsControl.ItemTemplate>
                        </ItemsControl>
                    </ScrollViewer>
                </Grid>
            </Panel>
        </Border>

        <StackPanel Grid.Row="4"
                    Orientation="Horizontal"
                    HorizontalAlignment="Right"
                    Spacing="10">
            <Button Content="Continuar"
                    IsDefault="True"
                    Command="{Binding ContinueButtonClickedCommand}"
                    MinWidth="110"
                    HorizontalContentAlignment="Center"
                    IsEnabled="{Binding ContinueButtonEnabled}"
                    Classes="Primary"/>
            <Button Content="Cancelar"
                    IsCancel="True"
                    Command="{Binding $parent[Window].Close}"
                    MinWidth="100"
                    HorizontalContentAlignment="Center"/>
        </StackPanel>
    </Grid>
</Window>
'@
Write-Utf8 (Join-Path $Root "YoutubeApp/Views/AddLinkWindow.axaml") $addLinkView

$main = Join-Path $Root "YoutubeApp/Views/MainWindow.axaml"
$mainText = Read-Utf8 $main
$replacements = [ordered]@{
    'Title="Youtube Downloader"' = 'Title="Conversor de Video e Audio"'
    'Header="Downloads"' = 'Header="Downloads"'
    'Header="Channels"' = 'Header="Canais"'
    'ToolTip.Tip="Exit"' = 'ToolTip.Tip="Sair"'
    'ToolTip.Tip="About"' = 'ToolTip.Tip="Sobre"'
    'ToolTip.Tip="Settings"' = 'ToolTip.Tip="Configuracoes"'
    'ToolTip.Tip="Add Link(s)"' = 'ToolTip.Tip="Adicionar links"'
    'ToolTip.Tip="Grabber List"' = 'ToolTip.Tip="Fila de processamento"'
}
foreach ($pair in $replacements.GetEnumerator()) {
    $mainText = $mainText.Replace($pair.Key, $pair.Value)
}
Write-Utf8 $main $mainText

$mainVm = Join-Path $Root "YoutubeApp/ViewModels/MainWindowViewModel.cs"
$mainVmText = Read-Utf8 $mainVm
$mainVmText = $mainVmText.Replace('Title = "Downloader Error", Message = "Failed to connect to Aria2"',
                                  'Title = "Erro do baixador", Message = "Nao foi possivel iniciar o Aria2"')
Write-Utf8 $mainVm $mainVmText

$aboutView = Join-Path $Root "YoutubeApp/Views/AboutWindow.axaml"
if (Test-Path $aboutView) {
    $aboutText = Read-Utf8 $aboutView
    $aboutText = $aboutText.Replace('Title="About"', 'Title="Sobre"')
    Write-Utf8 $aboutView $aboutText
}

$csproj = Join-Path $Root "YoutubeApp/YoutubeApp.csproj"
$projText = Read-Utf8 $csproj
$projText = $projText.Replace('<Version>0.3.11</Version>', '<Version>1.0.0-ptbr</Version>')
Write-Utf8 $csproj $projText

Write-Host "Customizacoes PT-BR e fila de 100 links aplicadas com sucesso."
